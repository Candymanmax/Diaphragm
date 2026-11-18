"""Manage the optional PyTorch runtime used by the packaged desktop app.

The GUI package deliberately does not contain PyTorch.  This module keeps the
first-run setup policy small and standard-library-only so it can run before
the heavier speech-generation modules are imported.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys

from modules.platform_paths import local_app_data_root


PYTORCH_VERSION = "2.6.0"
TORCHAUDIO_VERSION = "2.6.0"
CUDA_VERSION = "12.6"
# PyTorch contains CPython-native extension modules.  The downloaded runtime
# must therefore use the same Python major/minor version and architecture as
# the packaged application that imports it.
RUNTIME_PYTHON_VERSION = (sys.version_info.major, sys.version_info.minor)
RUNTIME_ARCHITECTURE_BITS = struct.calcsize("P") * 8
RUNTIME_MACHINE = platform.machine().lower()
RUNTIME_FOLDER_NAME = "runtime"
RUNTIME_PYTHON_ENVIRONMENT = "DIAPHRAGM_RUNTIME_PYTHON"

CPU_INDEX_URL = "https://download.pytorch.org/whl/cpu"
CUDA_INDEX_URL = "https://download.pytorch.org/whl/cu126"
MACOS_INDEX_URL = "https://pypi.org/simple"
_DLL_DIRECTORY_HANDLES = {}


@dataclass(frozen=True)
class RuntimeSpec:
    """The exact accelerator build that should be installed."""

    variant: str
    display_name: str
    index_url: str
    torch_suffix: str | None
    cuda_version: str | None = None


CPU_RUNTIME = RuntimeSpec(
    variant="cpu",
    display_name="CPU",
    index_url=CPU_INDEX_URL,
    torch_suffix="+cpu",
)
CUDA_RUNTIME = RuntimeSpec(
    variant="cuda",
    display_name="CUDA 12.6",
    index_url=CUDA_INDEX_URL,
    torch_suffix="+cu126",
    cuda_version=CUDA_VERSION,
)
# The macOS wheel supports CPU and Metal in the same package, and has no
# Windows/Linux-style +cpu suffix. MPS availability is an inference choice,
# not a prerequisite for installing or reusing this runtime.
MACOS_RUNTIME = RuntimeSpec(
    variant="macos",
    display_name="macOS",
    index_url=MACOS_INDEX_URL,
    torch_suffix=None,
)


@dataclass(frozen=True)
class PythonCommand:
    """A Python executable plus optional launcher arguments."""

    program: str
    arguments: tuple[str, ...] = ()


@dataclass(frozen=True)
class RuntimeSetupResult:
    """Outcome returned to the desktop entry point after first-run setup."""

    ready: bool
    cancelled: bool = False


def _default_data_root():
    return local_app_data_root() / "Diaphragm"


def detect_runtime_spec():
    """Select native macOS wheels, or CPU/CUDA wheels on other platforms."""

    if sys.platform == "darwin":
        return MACOS_RUNTIME

    nvidia_smi = shutil.which("nvidia-smi")
    if nvidia_smi:
        try:
            result = subprocess.run(
                [nvidia_smi, "-L"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            result = None

        if result is not None and result.returncode == 0 and result.stdout.strip():
            return CUDA_RUNTIME

    return CPU_RUNTIME


def _python_abi_check_code():
    return (
        "import platform, struct, sys; "
        f"assert sys.version_info[:2] == {RUNTIME_PYTHON_VERSION!r}; "
        f"assert struct.calcsize('P') * 8 == {RUNTIME_ARCHITECTURE_BITS!r}; "
        f"assert platform.machine().lower() == {RUNTIME_MACHINE!r}; "
    )


def _version_check_command(program, arguments=()):
    return [
        str(program),
        *[str(argument) for argument in arguments],
        "-c",
        _python_abi_check_code(),
    ]


def _python_command_is_usable(command):
    try:
        result = subprocess.run(
            _version_check_command(command.program, command.arguments),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def find_bootstrap_python():
    """Find a Python matching the packaged app's native-extension ABI."""

    candidates = []
    if not getattr(sys, "frozen", False):
        candidates.append(PythonCommand(sys.executable))

    launcher = shutil.which("py") if sys.platform == "win32" else None
    if launcher:
        version = ".".join(str(part) for part in RUNTIME_PYTHON_VERSION)
        for launcher_argument in (f"-{version}", "-3"):
            candidates.append(PythonCommand(launcher, (launcher_argument,)))

    version = ".".join(str(part) for part in RUNTIME_PYTHON_VERSION)
    for executable in (f"python{version}", "python", "python3"):
        resolved = shutil.which(executable)
        if resolved:
            candidates.append(PythonCommand(resolved))

    if sys.platform == "darwin":
        # Finder-launched apps often lack Homebrew/python.org entries in PATH.
        for directory in (
            Path("/opt/homebrew/bin"),
            Path("/usr/local/bin"),
            Path(f"/Library/Frameworks/Python.framework/Versions/{version}/bin"),
        ):
            executable = directory / f"python{version}"
            if executable.is_file():
                candidates.append(PythonCommand(str(executable)))

    seen = set()
    for candidate in candidates:
        identity = (os.path.normcase(str(candidate.program)), candidate.arguments)
        if identity in seen:
            continue
        seen.add(identity)
        if _python_command_is_usable(candidate):
            return candidate

    return None


def runtime_python_path(runtime_root):
    runtime_root = Path(runtime_root).expanduser().resolve()
    if os.name == "nt":
        return runtime_root / "Scripts" / "python.exe"
    return runtime_root / "bin" / "python"


def _absolute_python_path(python_path):
    # Resolving bin/python itself follows a venv's symlink to the base Python,
    # losing both the environment during validation and its package directory.
    python_path = Path(python_path).expanduser()
    return python_path.parent.resolve() / python_path.name


def _site_packages_for(python_path):
    python_path = _absolute_python_path(python_path)
    runtime_root = python_path.parent.parent
    if os.name == "nt":
        return runtime_root / "Lib" / "site-packages"

    version = ".".join(str(part) for part in RUNTIME_PYTHON_VERSION)
    return runtime_root / "lib" / f"python{version}" / "site-packages"


def activate_runtime_imports(python_path=None):
    """Put an installed runtime ahead of the frozen app's import path.

    The DLL-directory handles must remain alive for the lifetime of the
    process, otherwise Windows may unload the CUDA/Torch native libraries
    before the generation worker imports them.
    """

    candidate = python_path or os.environ.get(RUNTIME_PYTHON_ENVIRONMENT)
    if not candidate:
        return None

    candidate = _absolute_python_path(candidate)
    if not candidate.is_file():
        raise RuntimeError(f"The configured runtime Python is missing: {candidate}")

    site_packages = _site_packages_for(candidate)
    if not site_packages.is_dir():
        raise RuntimeError(
            f"The configured runtime is incomplete: {site_packages} is missing"
        )

    site_string = str(site_packages)
    sys.path[:] = [entry for entry in sys.path if entry != site_string]
    sys.path.insert(0, site_string)

    torch_lib = site_packages / "torch" / "lib"
    if os.name == "nt" and torch_lib.is_dir():
        add_dll_directory = getattr(os, "add_dll_directory", None)
        if add_dll_directory is not None:
            key = str(torch_lib).casefold()
            if key not in _DLL_DIRECTORY_HANDLES:
                _DLL_DIRECTORY_HANDLES[key] = add_dll_directory(str(torch_lib))

    os.environ[RUNTIME_PYTHON_ENVIRONMENT] = str(candidate)
    os.environ["DIAPHRAGM_RUNTIME_SITE_PACKAGES"] = site_string
    os.environ["DIAPHRAGM_RUNTIME_TORCH_LIB"] = str(torch_lib)
    return candidate


class RuntimeManager:
    """Resolve, validate, and describe the app-owned speech runtime."""

    def __init__(self, data_root=None, *, spec=None):
        self.data_root = (
            Path(data_root).expanduser().resolve()
            if data_root is not None
            else _default_data_root()
        )
        self.root = self.data_root / RUNTIME_FOLDER_NAME
        self.spec = spec or detect_runtime_spec()

    @property
    def python_path(self):
        return runtime_python_path(self.root)

    def setup_error(self):
        """Explain unsupported macOS architectures before attempting pip."""

        if sys.platform == "darwin" and RUNTIME_MACHINE != "arm64":
            return (
                f"PyTorch {PYTORCH_VERSION} on macOS requires Apple Silicon "
                "(arm64). Use an arm64 build of Diaphragm and Python; Intel "
                "and Rosetta runtimes are not supported."
            )
        return None

    def candidate_paths(self):
        candidates = []
        configured = os.environ.get(RUNTIME_PYTHON_ENVIRONMENT)
        if configured:
            candidates.append(_absolute_python_path(configured))
        if not getattr(sys, "frozen", False):
            candidates.append(_absolute_python_path(sys.executable))
        candidates.append(self.python_path)

        unique = []
        seen = set()
        for candidate in candidates:
            identity = os.path.normcase(str(candidate))
            if identity in seen:
                continue
            seen.add(identity)
            unique.append(candidate)
        return tuple(unique)

    def ready_python(self):
        for candidate in self.candidate_paths():
            if candidate.is_file() and self.validate(candidate):
                return candidate
        return None

    def validate(self, python_path):
        """Verify Python ABI, pinned packages, and the accelerator build."""

        python_path = _absolute_python_path(python_path)
        if not python_path.is_file():
            return False

        code = self._verification_code()

        try:
            result = subprocess.run(
                [str(python_path), "-c", code],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=45,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return result.returncode == 0

    def bootstrap_command(self):
        return find_bootstrap_python()

    def venv_command(self, bootstrap, *, clear=False):
        if bootstrap is None:
            raise RuntimeError("A supported Python installation was not found")
        arguments = list(bootstrap.arguments)
        arguments.extend(("-m", "venv"))
        if clear:
            arguments.append("--clear")
        arguments.append(str(self.root))
        return bootstrap.program, tuple(arguments)

    def install_command(self):
        return (
            str(self.python_path),
            (
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-input",
                "--progress-bar",
                "on",
                "--upgrade",
                "--force-reinstall",
                "--no-cache-dir",
                f"torch=={PYTORCH_VERSION}",
                f"torchaudio=={TORCHAUDIO_VERSION}",
                "--index-url",
                self.spec.index_url,
            ),
        )

    def _verification_code(self):
        code = _python_abi_check_code() + (
            "import torch, torchaudio; "
            f"assert torch.__version__.split('+', 1)[0] == {PYTORCH_VERSION!r}; "
            f"assert torchaudio.__version__.split('+', 1)[0] == {TORCHAUDIO_VERSION!r}; "
        )
        if self.spec.torch_suffix is not None:
            code += (
                f"assert torch.__version__.endswith({self.spec.torch_suffix!r}); "
                f"assert torchaudio.__version__.endswith({self.spec.torch_suffix!r}); "
            )
        if self.spec.variant == "cuda":
            code += (
                f"assert torch.version.cuda == {self.spec.cuda_version!r}; "
                "assert torch.cuda.is_available();"
            )
        else:
            code += (
                "assert torch.version.cuda is None; "
                "assert not torch.cuda.is_available();"
            )
        return code

    def verify_command(self):
        return str(self.python_path), ("-c", self._verification_code())

    def activate(self, python_path=None):
        return activate_runtime_imports(python_path or self.python_path)


__all__ = [
    "CPU_INDEX_URL",
    "CPU_RUNTIME",
    "CUDA_INDEX_URL",
    "CUDA_RUNTIME",
    "CUDA_VERSION",
    "MACOS_INDEX_URL",
    "MACOS_RUNTIME",
    "PYTORCH_VERSION",
    "PythonCommand",
    "RUNTIME_FOLDER_NAME",
    "RUNTIME_ARCHITECTURE_BITS",
    "RUNTIME_MACHINE",
    "RUNTIME_PYTHON_VERSION",
    "RUNTIME_PYTHON_ENVIRONMENT",
    "RuntimeManager",
    "RuntimeSetupResult",
    "RuntimeSpec",
    "TORCHAUDIO_VERSION",
    "activate_runtime_imports",
    "detect_runtime_spec",
    "find_bootstrap_python",
    "runtime_python_path",
]
