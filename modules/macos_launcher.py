"""Bootstrap the macOS source checkout without importing GUI dependencies."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import platform
import plistlib
import shutil
import subprocess
import sys

from modules.runtime_manager import (
    MACOS_INDEX_URL,
    MACOS_RUNTIME,
    RUNTIME_PYTHON_ENVIRONMENT,
    RuntimeManager,
)


def application_executable(python):
    """Give source launches their own bundle identity without editing Python."""
    source = Path(sys.base_prefix) / "Resources" / "Python.app" / "Contents" / "MacOS" / "Python"
    if not source.is_file():
        return python
    contents = python.parent.parent / "Diaphragm.app" / "Contents"
    executable = contents / "MacOS" / "Diaphragm"
    executable.parent.mkdir(parents=True, exist_ok=True)
    changed = False
    if not executable.exists() or source.stat().st_mtime > executable.stat().st_mtime:
        shutil.copy2(source, executable)
        changed = True
    metadata = {
        "CFBundleName": "Diaphragm",
        "CFBundleDisplayName": "Diaphragm",
        "CFBundleIdentifier": "com.diaphragm.desktop",
        "CFBundleExecutable": "Diaphragm",
        "CFBundlePackageType": "APPL",
        "CFBundleVersion": "1",
        "NSHighResolutionCapable": True,
    }
    info = contents / "Info.plist"
    payload = plistlib.dumps(metadata)
    if not info.exists() or info.read_bytes() != payload:
        info.write_bytes(payload)
        changed = True
    if changed:
        subprocess.run(["/usr/bin/codesign", "--force", "--sign", "-", str(contents.parent)], check=True)
    return executable


def prepare_environment(project_root):
    project_root = Path(project_root).resolve()
    environment = project_root / ".runtime"
    python = environment / "bin" / "python"
    marker = environment / ".diaphragm-requirements.sha256"
    requirements = project_root / "requirements.txt"
    fingerprint = hashlib.sha256(requirements.read_bytes()).hexdigest()

    def run(arguments):
        subprocess.run(arguments, cwd=project_root, check=True)

    if environment.exists():
        check = (
            "import platform, sys; assert sys.version_info[:2] == "
            f"{sys.version_info[:2]!r}; "
            f"assert platform.machine().lower() == {platform.machine().lower()!r}"
        )
        if not python.is_file() or subprocess.run(
            [str(python), "-c", check], cwd=project_root,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            check=False,
        ).returncode != 0:
            raise RuntimeError(
                "The project's .runtime environment is incompatible. Rename "
                "that folder and run launch.command again to create a fresh one."
            )
    else:
        print("Creating the isolated project environment in .runtime…", flush=True)
        run([sys.executable, "-m", "venv", str(environment)])

    manager = RuntimeManager(project_root, spec=MACOS_RUNTIME)
    dependencies_present = subprocess.run(
        [str(python), "-c", (
            "import importlib.util as u; "
            "names=('yaml','PySide6','torch','torchaudio','soundfile',"
            "'pyloudnorm','syntok','tqdm','chatterbox','keyring','numpy'); "
            "assert all(u.find_spec(name) is not None for name in names)"
        )],
        cwd=project_root, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, check=False,
    ).returncode == 0
    installed_fingerprint = marker.read_text().strip() if marker.is_file() else ""
    if installed_fingerprint != fingerprint or not dependencies_present or not manager.validate(python):
        marker.unlink(missing_ok=True)
        print("Installing macOS dependencies. First setup may take several minutes…", flush=True)
        run([
            str(python), "-m", "pip", "install", "--disable-pip-version-check",
            "--no-input", "--index-url", MACOS_INDEX_URL, "-r", str(requirements),
        ])
        run([str(python), "-m", "pip", "check"])
        if not manager.validate(python):
            raise RuntimeError("The installed macOS PyTorch runtime failed validation.")
        marker.write_text(fingerprint + "\n", encoding="utf-8")
    return python


def main(arguments=None):
    if sys.platform != "darwin" or platform.machine().lower() != "arm64" or sys.version_info[:2] != (3, 11):
        print("Use launch.command with arm64 Python 3.11 on macOS.", file=sys.stderr)
        return 1
    project_root = Path(__file__).resolve().parent.parent
    try:
        python = prepare_environment(project_root)
        environment = os.environ.copy()
        environment[RUNTIME_PYTHON_ENVIRONMENT] = str(python)
        executable = application_executable(python)
        # Preserve venv discovery when running its framework interpreter from
        # our named bundle instead of through the venv's Python stub.
        environment["PYTHONEXECUTABLE"] = str(python)
        print("Starting Diaphragm…", flush=True)
        result = subprocess.run(
            [str(executable), "-X", "faulthandler", str(project_root / "desktop_gui.py"),
             *(sys.argv[1:] if arguments is None else arguments)],
            cwd=project_root, env=environment, check=False,
        )
        if result.returncode:
            print(f"Diaphragm exited with code {result.returncode}.", file=sys.stderr)
        return result.returncode
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Diaphragm setup failed: {error}", file=sys.stderr)
        print("Check your connection and Git installation, then run launch.command again.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
