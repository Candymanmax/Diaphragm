from __future__ import annotations

import argparse
import multiprocessing
from pathlib import Path
import sys

from PySide6.QtCore import QLockFile, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from harness_ui.dialogs import AppDialog, RuntimeSetupDialog
from harness_ui.theme import (
    APP_STYLESHEET,
    load_bundled_ui_font,
    preferred_ui_font,
)
from modules.app_settings import APP_VERSION, SettingsRepository
from modules.runtime_manager import activate_runtime_imports


APPLICATION_ICON_PATH = Path("harness_ui") / "assets" / "diaphragm_icon.ico"
APPLICATION_ICON_FALLBACK_PATH = (
    Path("harness_ui") / "assets" / "diaphragm_icon.svg"
)
WINDOWS_APP_USER_MODEL_ID = "Diaphragm.Application"


def _default_install_root():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent


def _application_icon_path():
    bundle_root = Path(
        getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)
    )

    for relative_path in (
        APPLICATION_ICON_PATH,
        APPLICATION_ICON_FALLBACK_PATH,
    ):
        candidate = bundle_root / relative_path
        if candidate.is_file():
            return candidate

    return bundle_root / APPLICATION_ICON_PATH


def _set_windows_app_identity():
    """Give batch-launched windows their own Windows taskbar identity."""

    if sys.platform != "win32":
        return

    try:
        import ctypes

        set_app_id = (
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        )
        set_app_id.argtypes = [ctypes.c_wchar_p]
        set_app_id.restype = ctypes.c_long
        set_app_id(WINDOWS_APP_USER_MODEL_ID)
    except (AttributeError, OSError):
        # The Qt window icon remains the fallback if the Windows shell API is
        # unavailable in an alternate runtime.
        return


def _bundled_defaults_file(install_root):
    installed = Path(install_root) / "config.default.yaml"

    if installed.is_file():
        return installed

    bundled = Path(getattr(sys, "_MEIPASS", "")) / "config.default.yaml"
    return bundled if bundled.is_file() else installed


def _parser():
    parser = argparse.ArgumentParser(description="Local Diaphragm desktop app")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser


def _run_model_download(arguments):
    """Dispatch packaged model downloads through the already bundled app."""

    activate_runtime_imports()
    from modules.model_download import main as model_download_main

    return model_download_main(arguments)


def _run_model_inventory(arguments):
    """Dispatch packaged model verification/removal through the app."""

    from modules.model_inventory.cli import main as model_inventory_main

    return model_inventory_main(arguments)


def _smoke_test_runtime_imports():
    """Load native runtime modules inside the packaged interpreter."""

    import torch
    import torchaudio

    return f"torch={torch.__version__} torchaudio={torchaudio.__version__}"


def _smoke_test_generation_imports():
    """Load the bundled Chatterbox import graph and its native dependencies."""

    from chatterbox import ChatterboxTTS
    from perth import PerthImplicitWatermarker

    # Importing Perth alone does not read its bundled configuration/weights.
    # Construct it to catch missing package data before publishing a build.
    watermarker = PerthImplicitWatermarker()
    return (
        f"chatterbox={ChatterboxTTS.__name__} "
        f"watermarker={type(watermarker).__name__}"
    )


def main(argv=None):
    raw_arguments = list(sys.argv[1:] if argv is None else argv)
    if raw_arguments and raw_arguments[0] == "--model-download":
        return _run_model_download(raw_arguments[1:])
    if raw_arguments and raw_arguments[0] == "--model-inventory":
        return _run_model_inventory(raw_arguments[1:])

    args = _parser().parse_args(raw_arguments)
    install_root = _default_install_root()
    _set_windows_app_identity()
    application = QApplication.instance() or QApplication(sys.argv[:1])
    application.setApplicationName("Diaphragm")
    application.setApplicationVersion(APP_VERSION)
    application.setOrganizationName("Diaphragm")
    application.setStyle("Fusion")
    load_bundled_ui_font()
    application_icon_path = _application_icon_path()
    application_icon = QIcon(str(application_icon_path))

    if not application_icon.isNull():
        application.setWindowIcon(application_icon)

    application.setFont(
        preferred_ui_font()
    )
    application.setStyleSheet(APP_STYLESHEET)

    settings_repository = SettingsRepository.for_application(
        install_root,
        defaults_file=_bundled_defaults_file(install_root),
    )
    lock_path = settings_repository.paths.data_root / ".desktop.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(lock_path))
    lock.setStaleLockTime(10000)

    if not lock.tryLock(100):
        AppDialog.information(
            None,
            "Diaphragm is already open",
            "Use the existing Diaphragm window. Only one instance can "
            "manage the local generation worker at a time.",
        )
        return 0

    try:
        runtime_result = RuntimeSetupDialog.ensure(
            settings_repository.paths.data_root,
        )
        if not runtime_result.ready:
            return 0 if runtime_result.cancelled else 1

        # Import the main window only after the selected external runtime has
        # been activated.  This keeps PyTorch out of the packaged executable.
        from harness_ui.main_window import HarnessMainWindow

        window = HarnessMainWindow(
            settings_repository=settings_repository,
            app_paths=settings_repository.paths,
        )
        if not application_icon.isNull():
            window.setWindowIcon(application_icon)

        if args.smoke_test:
            runtime_summary = _smoke_test_runtime_imports()
            generation_summary = _smoke_test_generation_imports()
            window.show()
            application.processEvents()
            print(
                f"desktop-smoke-ok size={window.size().width()}x"
                f"{window.size().height()} tabs="
                f"{window.workspace_view.header.work_tabs.count()} "
                f"{runtime_summary} {generation_summary}"
            )
            window.close()
            return 0

        window.show()
        QTimer.singleShot(0, window.job_controller.initialize_startup_job)
        return application.exec()
    finally:
        lock.unlock()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
