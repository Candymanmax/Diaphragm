"""Build and check the Apple Silicon application used by macOS CI."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform
import plistlib
import subprocess
import sys
import tempfile


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARCHIVE_NAME = "Diaphragm-macos-arm64.zip"


def check_host():
    if sys.platform != "darwin" or platform.machine().lower() != "arm64":
        raise RuntimeError("Build and verify this package on an Apple Silicon Mac.")
    if sys.version_info[:2] != (3, 11):
        raise RuntimeError("The macOS package requires Python 3.11.")


def check_bundle(bundle):
    executable = bundle / "Contents/MacOS/Diaphragm"
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise RuntimeError(f"The packaged executable is missing or not executable: {executable}")
    architectures = subprocess.check_output(
        ["/usr/bin/lipo", "-archs", str(executable)], text=True,
    ).strip()
    if architectures != "arm64":
        raise RuntimeError(f"Expected an arm64 executable, found {architectures!r}.")
    with (bundle / "Contents/Info.plist").open("rb") as stream:
        metadata = plistlib.load(stream)
    if metadata.get("CFBundleIdentifier") != "com.diaphragm.desktop":
        raise RuntimeError("The app bundle identifier is incorrect.")
    for relative in (
        "config.default.yaml",
        "harness_ui/assets/diaphragm_icon.svg",
        "harness_ui/assets/icons/play.svg",
        "harness_ui/assets/fonts/Inter[opsz,wght].ttf",
    ):
        if not (bundle / "Contents/Resources" / relative).is_file():
            raise RuntimeError(f"A packaged resource is missing: {relative}")
    if not any(path.is_symlink() for path in bundle.rglob("*")):
        raise RuntimeError("The PyInstaller bundle's symbolic links were not preserved.")
    subprocess.run(
        ["/usr/bin/codesign", "--verify", "--deep", "--strict", str(bundle)],
        check=True,
    )


def build():
    subprocess.run(
        [
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
            "--onedir", "--windowed", "--name", "Diaphragm",
            # Use PyInstaller's default ad-hoc signing. An explicit identity
            # enables hardened runtime, which needs Developer ID signing and
            # a separate entitlement policy for the external speech runtime.
            "--target-arch", "arm64",
            "--osx-bundle-identifier", "com.diaphragm.desktop",
            "--distpath", str(PROJECT_ROOT / "dist"),
            "--workpath", str(PROJECT_ROOT / "build/macos/work"),
            "--specpath", str(PROJECT_ROOT / "build/macos"),
            "--icon", str(PROJECT_ROOT / "harness_ui/assets/diaphragm_icon.ico"),
            "--add-data", f"{PROJECT_ROOT / 'config.default.yaml'}:.",
            "--add-data", f"{PROJECT_ROOT / 'harness_ui/assets'}:harness_ui/assets",
            "--collect-all", "chatterbox", "--collect-all", "syntok",
            "--collect-binaries", "sklearn", "--collect-data", "perth",
            "--recursive-copy-metadata", "diffusers",
            "--recursive-copy-metadata", "transformers",
            "--hidden-import", "keyring.backends.macOS",
            "--exclude-module", "torch", "--exclude-module", "torchaudio",
            str(PROJECT_ROOT / "desktop_gui.py"),
        ],
        cwd=PROJECT_ROOT,
        check=True,
    )
    bundle = PROJECT_ROOT / "dist/Diaphragm.app"
    check_bundle(bundle)
    archive = PROJECT_ROOT / "dist" / ARCHIVE_NAME
    archive.unlink(missing_ok=True)
    # Archive the bundle before uploading: Actions' loose-file artifacts do
    # not preserve the executable permissions and symlinks required by .apps.
    subprocess.run(
        ["/usr/bin/ditto", "-c", "-k", "--sequesterRsrc", "--keepParent",
         str(bundle), str(archive)],
        check=True,
    )
    print(f"Created {archive}", flush=True)


def verify(archive, runtime_python):
    archive = Path(archive).expanduser().resolve()
    # Preserve a virtual environment's bin/python symlink instead of resolving
    # it to the base interpreter and losing its isolated site-packages.
    runtime_python = Path(os.path.abspath(Path(runtime_python).expanduser()))
    if not archive.is_file() or not runtime_python.is_file():
        raise RuntimeError("The package archive and smoke-runtime Python must both exist.")
    subprocess.run(
        [str(runtime_python), "-I", "-c",
         "import importlib.util; "
         "assert all(importlib.util.find_spec(name) is None for name in "
         "('chatterbox', 'PySide6', 'perth', 'transformers', 'diffusers')), "
         "'Use an isolated smoke runtime containing only torch and torchaudio dependencies'"],
        check=True,
    )
    with tempfile.TemporaryDirectory(prefix="Diaphragm-package-check-") as temporary:
        root = Path(temporary)
        installed = root / "Installed Application"
        subprocess.run(
            ["/usr/bin/ditto", "-x", "-k", str(archive), str(installed)],
            check=True,
        )
        bundle = installed / "Diaphragm.app"
        check_bundle(bundle)
        environment = os.environ.copy()
        for name in (
            "PYTHONPATH", "PYTHONHOME", "PYTHONEXECUTABLE", "__PYVENV_LAUNCHER__",
            "DYLD_LIBRARY_PATH", "DYLD_FRAMEWORK_PATH",
        ):
            environment.pop(name, None)
        home = root / "home"
        home.mkdir()
        environment.update(
            HOME=str(home),
            QT_QPA_PLATFORM="offscreen",
            PYTHONNOUSERSITE="1",
            DIAPHRAGM_RUNTIME_PYTHON=str(runtime_python),
        )
        # Run outside the checkout so source files and the build environment
        # cannot hide modules, data or metadata missing from the package.
        result = subprocess.run(
            [str(bundle / "Contents/MacOS/Diaphragm"), "--smoke-test"],
            cwd=root, env=environment, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, timeout=180,
        )
        print(result.stdout, flush=True)
        if result.returncode != 0 or "desktop-smoke-ok" not in result.stdout:
            raise RuntimeError(f"Packaged smoke test failed (exit {result.returncode}).")
    print("Extracted macOS package smoke test passed.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("build")
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("archive")
    verify_parser.add_argument("--runtime-python", required=True)
    arguments = parser.parse_args()
    check_host()
    if arguments.command == "build":
        build()
    else:
        verify(arguments.archive, arguments.runtime_python)


if __name__ == "__main__":
    main()
