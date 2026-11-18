"""Tests for deferred Windows and macOS runtime setup."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
import venv
from unittest.mock import patch

from modules import runtime_manager
from modules.platform_paths import local_app_data_root


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
            with self.subTest(name=name), patch.object(sys, "platform", "win32"), patch.object(
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

    def test_macos_uses_native_wheels_without_probing_cuda_or_importing_torch(self):
        with patch.object(sys, "platform", "darwin"), patch.object(
            runtime_manager.shutil, "which"
        ) as which, patch.object(
            runtime_manager.subprocess, "run"
        ) as run, patch.dict(sys.modules, {"torch": None}):
            self.assertEqual(
                runtime_manager.detect_runtime_spec(), runtime_manager.MACOS_RUNTIME
            )
        which.assert_not_called()
        run.assert_not_called()

    def test_macos_architecture_errors_explain_intel_and_rosetta_limitations(self):
        manager = runtime_manager.RuntimeManager(spec=runtime_manager.MACOS_RUNTIME)
        with patch.object(sys, "platform", "darwin"):
            with patch.object(runtime_manager, "RUNTIME_MACHINE", "arm64"):
                self.assertIsNone(manager.setup_error())
            with patch.object(runtime_manager, "RUNTIME_MACHINE", "x86_64"):
                error = manager.setup_error()
                self.assertIn("arm64", error)
                self.assertIn("Intel", error)
                self.assertIn("Rosetta", error)

        with patch.object(sys, "platform", "win32"), patch.object(
            runtime_manager, "RUNTIME_MACHINE", "amd64"
        ):
            self.assertIsNone(manager.setup_error())

    def test_settings_and_runtime_share_platform_data_roots(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary).resolve()
            scenarios = (
                ("darwin", {}, home / "Library" / "Application Support"),
                ("linux", {}, home / ".local" / "share"),
                ("win32", {"LOCALAPPDATA": str(home / "Local")}, home / "Local"),
                ("darwin", {"LOCALAPPDATA": str(home / "override")}, home / "override"),
            )
            for platform_name, environment, expected in scenarios:
                with self.subTest(platform=platform_name, env=environment), patch.object(
                    sys, "platform", platform_name
                ), patch.dict(os.environ, environment, clear=True), patch.object(
                    Path, "home", return_value=home
                ):
                    self.assertEqual(local_app_data_root(), expected)
                    manager = runtime_manager.RuntimeManager(spec=runtime_manager.CPU_RUNTIME)
                    self.assertEqual(manager.data_root, expected / "Diaphragm")

    def test_bootstrap_python_requires_the_app_python_abi(self):
        def executable(name):
            return "C:/Python/py.exe" if name == "py" else None

        expected_version = ".".join(
            str(part) for part in runtime_manager.RUNTIME_PYTHON_VERSION
        )
        expected_argument = f"-{expected_version}"

        with patch.object(sys, "platform", "win32"), patch.object(
            sys, "frozen", True, create=True
        ), patch.object(
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

    def test_macos_finder_launch_finds_homebrew_and_python_org_without_path(self):
        version = ".".join(str(part) for part in runtime_manager.RUNTIME_PYTHON_VERSION)
        locations = (
            f"/opt/homebrew/bin/python{version}",
            f"/usr/local/bin/python{version}",
            f"/Library/Frameworks/Python.framework/Versions/{version}/bin/python{version}",
        )
        for location in locations:
            with self.subTest(location=location), patch.object(
                sys, "platform", "darwin"
            ), patch.object(sys, "frozen", True, create=True), patch.object(
                runtime_manager.shutil, "which", return_value=None
            ), patch.object(
                Path, "is_file", autospec=True,
                # The matrix runs this macOS policy test on Windows too.
                side_effect=lambda p: p == Path(location),
            ), patch.object(
                runtime_manager, "_python_command_is_usable", return_value=True
            ):
                command = runtime_manager.find_bootstrap_python()
                self.assertEqual(command, runtime_manager.PythonCommand(str(Path(location))))

    def test_bootstrap_rejects_wrong_architecture_even_when_both_are_64_bit(self):
        command = runtime_manager.PythonCommand(sys.executable)
        self.assertTrue(runtime_manager._python_command_is_usable(command))
        other_machine = "x86_64" if runtime_manager.RUNTIME_MACHINE == "arm64" else "arm64"
        with patch.object(runtime_manager, "RUNTIME_MACHINE", other_machine):
            self.assertFalse(runtime_manager._python_command_is_usable(command))

    def test_bootstrap_python_returns_none_when_no_interpreter_is_available(self):
        with patch.object(sys, "platform", "win32"), patch.object(
            sys, "frozen", True, create=True
        ), patch.object(
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

    def test_macos_install_pins_native_torch_and_torchaudio_from_pypi(self):
        with tempfile.TemporaryDirectory() as temporary:
            manager = runtime_manager.RuntimeManager(temporary, spec=runtime_manager.MACOS_RUNTIME)
            _program, arguments = manager.install_command()
            self.assertIn("torch==2.6.0", arguments)
            self.assertIn("torchaudio==2.6.0", arguments)
            self.assertEqual(
                arguments[arguments.index("--index-url") + 1],
                "https://pypi.org/simple",
            )
            self.assertNotIn(runtime_manager.CPU_INDEX_URL, arguments)
            self.assertNotIn(runtime_manager.CUDA_INDEX_URL, arguments)

    def test_verification_accepts_native_macos_and_rejects_incompatible_builds(self):
        scenarios = (
            (runtime_manager.MACOS_RUNTIME, "2.6.0", "2.6.0", None, False, True),
            (runtime_manager.MACOS_RUNTIME, "2.5.1", "2.6.0", None, False, False),
            (runtime_manager.MACOS_RUNTIME, "2.6.0", "2.5.1", None, False, False),
            (runtime_manager.MACOS_RUNTIME, "2.6.0+cu126", "2.6.0+cu126", "12.6", True, False),
            (runtime_manager.CPU_RUNTIME, "2.6.0+cpu", "2.6.0+cpu", None, False, True),
            (runtime_manager.CPU_RUNTIME, "2.6.0", "2.6.0", None, False, False),
            (runtime_manager.CPU_RUNTIME, "2.6.0+cpu", "2.6.0+cu126", None, False, False),
            (runtime_manager.CUDA_RUNTIME, "2.6.0+cu126", "2.6.0+cu126", "12.6", True, True),
            (runtime_manager.CUDA_RUNTIME, "2.6.0+cu126", "2.6.0+cpu", "12.6", True, False),
            (runtime_manager.CUDA_RUNTIME, "2.6.0+cu126", "2.6.0+cu126", "12.6", False, False),
            (runtime_manager.CUDA_RUNTIME, "2.6.0+cu126", "2.6.0+cu126", "12.4", True, False),
        )
        with tempfile.TemporaryDirectory() as temporary:
            for scenario in scenarios:
                spec, torch_version, audio_version, cuda_version, cuda_available, accepted = scenario
                with self.subTest(
                    spec=spec.variant, torch=torch_version, audio=audio_version,
                    cuda=cuda_version, gpu=cuda_available,
                ):
                    manager = runtime_manager.RuntimeManager(temporary, spec=spec)
                    _program, arguments = manager.verify_command()
                    torch = SimpleNamespace(
                        __version__=torch_version,
                        version=SimpleNamespace(cuda=cuda_version),
                        cuda=SimpleNamespace(is_available=lambda: cuda_available),
                    )
                    with patch.dict(sys.modules, {
                        "torch": torch,
                        "torchaudio": SimpleNamespace(__version__=audio_version),
                    }):
                        # Execute the actual verification program, including imports
                        # and assertions. No MPS API is required for CPU fallback.
                        if accepted:
                            exec(arguments[-1], {})
                        else:
                            with self.assertRaises(AssertionError):
                                exec(arguments[-1], {})

    @unittest.skipIf(os.name == "nt", "POSIX venv interpreter symlinks")
    def test_symlinked_venv_is_validated_activated_and_reused_without_losing_packages(self):
        with tempfile.TemporaryDirectory() as temporary:
            manager = runtime_manager.RuntimeManager(temporary, spec=runtime_manager.MACOS_RUNTIME)
            venv.EnvBuilder(with_pip=False, symlinks=True).create(manager.root)
            python_path = manager.python_path
            self.assertTrue(python_path.is_symlink())
            version = ".".join(str(part) for part in runtime_manager.RUNTIME_PYTHON_VERSION)
            site_packages = manager.root / "lib" / f"python{version}" / "site-packages"
            # Lightweight stand-ins prove that validation really imports from
            # the isolated venv rather than the base interpreter's packages.
            (site_packages / "torch.py").write_text(
                "from types import SimpleNamespace\n"
                "__version__ = '2.6.0'\n"
                "version = SimpleNamespace(cuda=None)\n"
                "cuda = SimpleNamespace(is_available=lambda: False)\n",
                encoding="utf-8",
            )
            (site_packages / "torchaudio.py").write_text(
                "__version__ = '2.6.0'\n", encoding="utf-8"
            )
            with patch.dict(
                os.environ, {runtime_manager.RUNTIME_PYTHON_ENVIRONMENT: str(python_path)}
            ), patch.object(
                sys, "path", list(sys.path)
            ):
                self.assertTrue(manager.validate(python_path))
                self.assertEqual(manager.ready_python(), python_path)
                self.assertEqual(manager.activate(python_path), python_path)
                self.assertEqual(sys.path[0], str(site_packages))
                self.assertEqual(
                    os.environ[runtime_manager.RUNTIME_PYTHON_ENVIRONMENT], str(python_path)
                )
                # A worker inherits this environment and must keep the same venv.
                self.assertEqual(runtime_manager.activate_runtime_imports(), python_path)

    @unittest.skipIf(os.name == "nt", "POSIX site-packages layout")
    def test_activation_does_not_reuse_site_packages_from_another_python_version(self):
        with tempfile.TemporaryDirectory() as temporary:
            manager = runtime_manager.RuntimeManager(temporary, spec=runtime_manager.MACOS_RUNTIME)
            python_path = manager.python_path
            python_path.parent.mkdir(parents=True)
            python_path.write_bytes(b"python")
            (manager.root / "lib" / "python0.0" / "site-packages").mkdir(parents=True)
            with self.assertRaisesRegex(RuntimeError, "runtime is incomplete"):
                manager.activate(python_path)

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
                runtime_manager, "_site_packages_for", return_value=site_packages.resolve()
            ), patch.object(
                runtime_manager, "os", SimpleNamespace(
                    name="nt", environ=os.environ, add_dll_directory=lambda path: None
                )
            ), patch.object(
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
