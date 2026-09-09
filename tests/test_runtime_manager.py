"""Tests for the deferred CPU/CUDA runtime setup policy."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from modules import runtime_manager


class RuntimeManagerTests(unittest.TestCase):
    def test_gpu_detection_requires_a_reported_nvidia_device(self):
        scenarios = (
            ("missing executable", None, None, None, runtime_manager.CPU_RUNTIME),
            (
                "reported GPU",
                "nvidia-smi",
                SimpleNamespace(returncode=0, stdout="GPU 0"),
                None,
                runtime_manager.CUDA_RUNTIME,
            ),
            (
                "empty output",
                "nvidia-smi",
                SimpleNamespace(returncode=0, stdout=""),
                None,
                runtime_manager.CPU_RUNTIME,
            ),
            (
                "failed command",
                "nvidia-smi",
                SimpleNamespace(returncode=1, stdout=""),
                None,
                runtime_manager.CPU_RUNTIME,
            ),
            (
                "launch error",
                "nvidia-smi",
                None,
                OSError("nvidia-smi unavailable"),
                runtime_manager.CPU_RUNTIME,
            ),
        )

        for name, executable, result, error, expected in scenarios:
            with self.subTest(name=name), patch.object(
                runtime_manager.shutil,
                "which",
                return_value=executable,
            ), patch.object(
                runtime_manager.subprocess,
                "run",
                return_value=result,
                side_effect=error,
            ) as run:
                self.assertEqual(runtime_manager.detect_runtime_spec(), expected)
                if executable is None:
                    run.assert_not_called()

    def test_bootstrap_python_requires_the_app_python_abi(self):
        def executable(name):
            return "C:/Python/py.exe" if name == "py" else None

        expected_version = ".".join(
            str(part) for part in runtime_manager.RUNTIME_PYTHON_VERSION
        )
        expected_argument = f"-{expected_version}"

        with patch.object(sys, "frozen", True, create=True), patch.object(
            runtime_manager.shutil,
            "which",
            side_effect=executable,
        ), patch.object(
            runtime_manager,
            "_python_command_is_usable",
            side_effect=lambda command: command.arguments == (
                expected_argument,
            ),
        ) as usable:
            command = runtime_manager.find_bootstrap_python()

        self.assertEqual(
            command,
            runtime_manager.PythonCommand(
                "C:/Python/py.exe",
                (expected_argument,),
            ),
        )
        self.assertEqual(
            [call.args[0].arguments for call in usable.call_args_list],
            [(expected_argument,)],
        )

        version_command = runtime_manager._version_check_command("python")
        self.assertIn(
            f"== {runtime_manager.RUNTIME_PYTHON_VERSION!r}",
            version_command[-1],
        )
        self.assertIn(
            str(runtime_manager.RUNTIME_ARCHITECTURE_BITS),
            version_command[-1],
        )

    def test_bootstrap_python_returns_none_when_no_interpreter_is_available(self):
        with patch.object(sys, "frozen", True, create=True), patch.object(
            runtime_manager.shutil,
            "which",
            return_value=None,
        ), patch.object(
            runtime_manager,
            "_python_command_is_usable",
        ) as usable:
            command = runtime_manager.find_bootstrap_python()

        self.assertIsNone(command)
        usable.assert_not_called()

    def test_runtime_commands_pin_the_accelerator_build(self):
        with tempfile.TemporaryDirectory() as temporary:
            manager = runtime_manager.RuntimeManager(
                temporary,
                spec=runtime_manager.CPU_RUNTIME,
            )
            bootstrap = runtime_manager.PythonCommand("python")

            program, venv_arguments = manager.venv_command(
                bootstrap,
                clear=True,
            )
            self.assertEqual(program, "python")
            self.assertEqual(venv_arguments[:3], ("-m", "venv", "--clear"))
            self.assertEqual(venv_arguments[-1], str(manager.root))

            install_program, install_arguments = manager.install_command()
            self.assertEqual(install_program, str(manager.python_path))
            self.assertIn("torch==2.6.0", install_arguments)
            self.assertIn("torchaudio==2.6.0", install_arguments)
            self.assertIn("https://download.pytorch.org/whl/cpu", install_arguments)

            cuda_manager = runtime_manager.RuntimeManager(
                temporary,
                spec=runtime_manager.CUDA_RUNTIME,
            )
            _verify_program, verify_arguments = cuda_manager.verify_command()
            self.assertIn("12.6", verify_arguments[-1])
            self.assertIn("torch.cuda.is_available()", verify_arguments[-1])

    def test_ready_python_can_use_the_ci_or_parent_runtime_override(self):
        with tempfile.TemporaryDirectory() as temporary:
            override = Path(temporary) / "python.exe"
            override.write_bytes(b"python")
            manager = runtime_manager.RuntimeManager(
                Path(temporary) / "app-data",
                spec=runtime_manager.CPU_RUNTIME,
            )

            with patch.dict(
                os.environ,
                {runtime_manager.RUNTIME_PYTHON_ENVIRONMENT: str(override)},
                clear=False,
            ), patch.object(manager, "validate", return_value=True):
                self.assertEqual(manager.ready_python(), override.resolve())

    def test_validate_handles_success_rejection_and_process_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            python_path = Path(temporary) / "python.exe"
            python_path.write_bytes(b"python")
            manager = runtime_manager.RuntimeManager(
                Path(temporary) / "app-data",
                spec=runtime_manager.CPU_RUNTIME,
            )

            with patch.object(
                runtime_manager.subprocess,
                "run",
                return_value=SimpleNamespace(returncode=0),
            ) as run:
                self.assertTrue(manager.validate(python_path))
                validation_code = run.call_args.args[0][-1]
                self.assertIn(runtime_manager.PYTORCH_VERSION, validation_code)
                self.assertIn(
                    f"== {runtime_manager.RUNTIME_PYTHON_VERSION!r}",
                    validation_code,
                )
                self.assertIn("not torch.cuda.is_available()", validation_code)

            with patch.object(
                runtime_manager.subprocess,
                "run",
                return_value=SimpleNamespace(returncode=1),
            ):
                self.assertFalse(manager.validate(python_path))

            with patch.object(
                runtime_manager.subprocess,
                "run",
                side_effect=OSError("cannot start runtime"),
            ):
                self.assertFalse(manager.validate(python_path))

            self.assertFalse(manager.validate(Path(temporary) / "missing.exe"))

    def test_activate_runtime_imports_adds_site_packages_and_dll_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            python_path = root / "Scripts" / "python.exe"
            site_packages = root / "Lib" / "site-packages"
            torch_lib = site_packages / "torch" / "lib"
            python_path.parent.mkdir(parents=True)
            python_path.write_bytes(b"python")
            torch_lib.mkdir(parents=True)

            with patch.object(sys, "path", list(sys.path)), patch.object(
                runtime_manager,
                "_DLL_DIRECTORY_HANDLES",
                {},
            ), patch.dict(os.environ, {}, clear=False), patch.object(
                runtime_manager.os,
                "add_dll_directory",
                return_value=object(),
                create=True,
            ) as add_dll_directory:
                activated = runtime_manager.activate_runtime_imports(
                    python_path
                )
                second_activation = runtime_manager.activate_runtime_imports(
                    python_path
                )

                self.assertEqual(second_activation, activated)
                self.assertEqual(activated, python_path.resolve())
                self.assertEqual(sys.path[0], str(site_packages.resolve()))
                self.assertEqual(
                    sys.path.count(str(site_packages.resolve())),
                    1,
                )
                if os.name == "nt":
                    add_dll_directory.assert_called_once_with(str(torch_lib.resolve()))

    def test_activate_runtime_imports_rejects_incomplete_runtimes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            missing_python = root / "missing" / "python.exe"

            with self.assertRaisesRegex(RuntimeError, "Python is missing"):
                runtime_manager.activate_runtime_imports(missing_python)

            python_path = root / "runtime" / "Scripts" / "python.exe"
            python_path.parent.mkdir(parents=True)
            python_path.write_bytes(b"python")

            with self.assertRaisesRegex(RuntimeError, "runtime is incomplete"):
                runtime_manager.activate_runtime_imports(python_path)

            with patch.dict(
                os.environ,
                {runtime_manager.RUNTIME_PYTHON_ENVIRONMENT: ""},
                clear=False,
            ):
                self.assertIsNone(runtime_manager.activate_runtime_imports())


if __name__ == "__main__":
    unittest.main()
