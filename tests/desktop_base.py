"""Shared Qt fixture and imports for feature-specific desktop test suites."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import shutil
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import wave

from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QDialog,
    QFrame,
    QLabel,
    QMainWindow,
    QPushButton,
)
from PySide6.QtCore import (
    QByteArray,
    QEvent,
    QPoint,
    QSettings,
    QSize,
    QTimer,
    Qt,
    QUrl,
)
from PySide6.QtGui import QHelpEvent, QIcon, QKeySequence

from desktop_gui import _application_icon_path
from harness_ui.main_window import HarnessMainWindow
from harness_ui.controllers import (
    SCRIPT_TEXT_ROLE,
    WINDOW_LAYOUT_KEYS,
    WINDOW_LAYOUT_SCHEMA_VERSION,
    relative_time,
)
from harness_ui.dialogs import NewJobDialog, UnsavedScriptDialog
from harness_ui.theme import (
    ACCENT_COLORS,
    ACCENT_END,
    ACCENT_START,
    APP_STYLESHEET,
    MAIN_BACKGROUND,
    MANTLE,
    PALETTE,
    TEAL,
    build_stylesheet,
    set_button_role,
)
from modules.adapters.registry import MODEL_DOWNLOAD_FILES
from modules.service import JobRequest
from harness_ui.widgets import EmptyStateWidget, JobCardWidget


class DesktopHarnessBase(unittest.TestCase):
    """Create one isolated application and private project per test."""

    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        # Match the application's path normalization. Windows can expose the
        # same temporary folder through its long name and its 8.3 short name.
        self.root = Path(self.temporary.name).resolve()
        (self.root / "input").mkdir()
        (self.root / "voices").mkdir()
        (self.root / "input" / "script.txt").write_text(
            "A desktop harness test.",
            encoding="utf-8",
        )
        (self.root / "voices" / "voice.wav").write_bytes(b"voice")
        (self.root / "config.default.yaml").write_text(
            "voice: voice.wav\nmodel: original\nlanguage: en\n",
            encoding="utf-8",
        )
        self.window = None

    def tearDown(self):
        window = getattr(self, "window", None)
        if window is not None:
            self.window.close()
            self.application.processEvents()


__all__ = [
    name for name in globals()
    if not name.startswith("__")
] + ["_application_icon_path"]
