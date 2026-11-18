"""Source launcher setup, reuse, and error recovery without downloads."""

import hashlib
import os
import plistlib
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from modules import macos_launcher as launcher


class MacOSLauncherTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="Diaphragm source ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.requirements = self.root / "requirements.txt"
        self.requirements.write_text("torch==2.6.0\n", encoding="utf-8")
        self.python = self.root / ".runtime" / "bin" / "python"
        self.marker = self.root / ".runtime" / ".diaphragm-requirements.sha256"

    def create_environment(self):
        self.python.parent.mkdir(parents=True)
        self.python.write_bytes(b"test interpreter")

    def mark_installed(self):
        self.marker.write_text(hashlib.sha256(self.requirements.read_bytes()).hexdigest())

    def test_first_launch_creates_environment_before_installing_and_verifying(self):
        def run(arguments, **kwargs):
            if arguments[1:3] == ["-m", "venv"]:
                self.create_environment()
            return SimpleNamespace(returncode=0)

        with patch.object(launcher.subprocess, "run", side_effect=run) as process, patch.object(
            launcher.RuntimeManager, "validate", return_value=True
        ):
            self.assertEqual(launcher.prepare_environment(self.root), self.python)
        commands = [call.args[0] for call in process.call_args_list]
        self.assertEqual(commands[0][1:3], ["-m", "venv"])
        install = next(command for command in commands if "install" in command)
        self.assertEqual(install[-1], str(self.requirements))
        self.assertIn("https://pypi.org/simple", install)
        self.assertIn([str(self.python), "-m", "pip", "check"], commands)
        self.assertTrue(self.marker.is_file())

    def test_unchanged_working_environment_launches_without_pip(self):
        self.create_environment()
        self.mark_installed()
        with patch.object(
            launcher.subprocess, "run", return_value=SimpleNamespace(returncode=0)
        ) as process, patch.object(launcher.RuntimeManager, "validate", return_value=True):
            self.assertEqual(launcher.prepare_environment(self.root), self.python)
        self.assertFalse(any("pip" in call.args[0] for call in process.call_args_list))

    def test_changed_requirements_are_installed_again(self):
        self.create_environment()
        self.mark_installed()
        self.requirements.write_text("torch==2.6.0\ntqdm\n", encoding="utf-8")
        with patch.object(
            launcher.subprocess, "run", return_value=SimpleNamespace(returncode=0)
        ) as process, patch.object(launcher.RuntimeManager, "validate", return_value=True):
            launcher.prepare_environment(self.root)
        self.assertTrue(any("install" in call.args[0] for call in process.call_args_list))

    def test_failed_install_does_not_leave_a_success_marker(self):
        self.create_environment()
        self.mark_installed()
        self.requirements.write_text("changed\n", encoding="utf-8")

        def run(arguments, **kwargs):
            if "install" in arguments:
                raise subprocess.CalledProcessError(1, arguments)
            return SimpleNamespace(returncode=0)

        with patch.object(launcher.subprocess, "run", side_effect=run):
            with self.assertRaises(subprocess.CalledProcessError):
                launcher.prepare_environment(self.root)
        self.assertFalse(self.marker.exists())

    def test_incompatible_existing_environment_is_preserved(self):
        environment = self.root / ".runtime"
        environment.mkdir()
        sentinel = environment / "keep.txt"
        sentinel.write_text("keep")
        with self.assertRaisesRegex(RuntimeError, "Rename that folder"):
            launcher.prepare_environment(self.root)
        self.assertEqual(sentinel.read_text(), "keep")

    def test_launch_forwards_arguments_runtime_and_exit_status(self):
        with patch.object(launcher.sys, "platform", "darwin"), patch.object(
            launcher.sys, "version_info", (3, 11, 9)
        ), patch.object(launcher.platform, "machine", return_value="arm64"), patch.object(
            launcher, "prepare_environment", return_value=self.python
        ), patch.object(
            launcher, "application_executable", return_value=self.python
        ), patch.object(
            launcher.subprocess, "run", return_value=SimpleNamespace(returncode=7)
        ) as process:
            self.assertEqual(launcher.main(["--smoke-test", "a path with spaces"]), 7)
        command = process.call_args.args[0]
        self.assertEqual(command[-2:], ["--smoke-test", "a path with spaces"])
        self.assertEqual(
            process.call_args.kwargs["env"][launcher.RUNTIME_PYTHON_ENVIRONMENT],
            str(self.python),
        )

    def test_source_bundle_has_its_own_name_and_preserves_original_python(self):
        source = self.root / "framework" / "Resources" / "Python.app" / "Contents" / "MacOS" / "Python"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"original interpreter")
        with patch.object(launcher.sys, "base_prefix", str(self.root / "framework")), patch.object(
            launcher.subprocess, "run"
        ) as sign:
            executable = launcher.application_executable(self.python)
            launcher.application_executable(self.python)
        metadata = plistlib.loads((executable.parent.parent / "Info.plist").read_bytes())
        self.assertEqual(metadata["CFBundleName"], "Diaphragm")
        self.assertEqual(metadata["CFBundleExecutable"], executable.name)
        self.assertEqual(source.read_bytes(), b"original interpreter")
        sign.assert_called_once()


if __name__ == "__main__":
    unittest.main()
