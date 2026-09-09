from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import shutil
import uuid

from PySide6.QtCore import QObject, QSettings, Signal

from modules.app_settings.models import (
    PREFERENCES_SCHEMA_VERSION,
    SUPPORTED_ACCENTS,
    AppPaths,
    AppPreferences,
    SettingsError,
)

def _local_app_data_root():
    configured = os.environ.get("LOCALAPPDATA")

    if configured:
        return Path(configured).expanduser().resolve()

    return (Path.home() / ".local" / "share").resolve()


def _atomic_copy(source, destination):
    source = Path(source)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.parent / (
        f".{destination.name}.{uuid.uuid4().hex}.tmp"
    )

    try:
        shutil.copy2(source, temporary)

        with temporary.open("r+b") as copied:
            os.fsync(copied.fileno())

        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"

    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as output:
            json.dump(value, output, indent=2, ensure_ascii=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())

        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


class SettingsRepository(QObject):
    """Typed wrapper around QSettings and the application's path policy."""

    changed = Signal(str, object)
    pathsChanged = Signal(object)
    resetRequested = Signal()

    def __init__(
        self,
        install_root,
        *,
        settings=None,
        defaults_file=None,
        data_root=None,
    ):
        super().__init__()
        self.install_root = Path(install_root).expanduser().resolve()
        self._data_root_override = (
            Path(data_root).expanduser().resolve()
            if data_root is not None
            else None
        )
        self.defaults_file = Path(
            defaults_file or self.install_root / "config.default.yaml"
        ).expanduser().resolve()
        self.settings = (
            settings
            if settings is not None
            else QSettings("Diaphragm", "Diaphragm")
        )

        self.paths = self._resolve_paths()
        self.paths.ensure_writable_folders()
        self._initialize_active_config()
        self.settings.setValue(
            "settings/schema_version",
            PREFERENCES_SCHEMA_VERSION,
        )
        self.settings.sync()

    @classmethod
    def for_application(cls, install_root, *, defaults_file=None, settings=None):
        return cls(
            install_root,
            settings=settings,
            defaults_file=defaults_file,
        )

    @classmethod
    def for_testing(cls, root, *, settings=None, defaults_file=None):
        """Create an isolated repository for tests without legacy paths."""

        root = Path(root).expanduser().resolve()
        if settings is None:
            settings = QSettings(
                str(root / "test-settings.ini"),
                QSettings.Format.IniFormat,
            )
        return cls(
            root,
            settings=settings,
            defaults_file=defaults_file,
            data_root=root,
        )

    def _resolve_paths(self):
        data_root = self._data_root_override or _local_app_data_root() / "Diaphragm"
        library_root = Path(
            self.settings.value(
                "paths/library_root",
                str(data_root),
            )
        )
        model_cache_root = Path(
            self.settings.value(
                "paths/model_cache_root",
                str(data_root / "models"),
            )
        )
        return AppPaths(
            install_root=self.install_root,
            data_root=data_root,
            library_root=library_root,
            model_cache_root=model_cache_root,
            defaults_file=self.defaults_file,
            config_file=data_root / "config.yaml",
            logs_root=data_root / "logs",
        )

    def _initialize_active_config(self):
        if self.paths.config_file.is_file():
            return

        if self.paths.defaults_file.is_file():
            _atomic_copy(self.paths.defaults_file, self.paths.config_file)

    def preferences(self):
        startup_behavior = str(
            self.settings.value("startup/behavior", "recent")
        )
        accent = str(self.settings.value("ui/accent", "teal"))

        if startup_behavior not in {"recent", "blank"}:
            startup_behavior = "recent"

        if accent not in SUPPORTED_ACCENTS:
            accent = "teal"

        try:
            low_disk_warning_gb = int(
                self.settings.value("storage/low_disk_warning_gb", 10)
            )
        except (TypeError, ValueError):
            low_disk_warning_gb = 10

        if not 1 <= low_disk_warning_gb <= 1024:
            low_disk_warning_gb = 10

        try:
            log_retention_days = int(
                self.settings.value("storage/log_retention_days", 14)
            )
        except (TypeError, ValueError):
            log_retention_days = 14

        if log_retention_days not in {0, 1, 3, 7, 14, 30, 60, 90}:
            log_retention_days = 14

        return AppPreferences(
            startup_behavior=startup_behavior,
            restore_layout=self.settings.value(
                "window/restore_layout", True, type=bool
            ),
            accent=accent,
            show_line_numbers=self.settings.value(
                "editor/show_line_numbers", True, type=bool
            ),
            sidebar_visible=self.settings.value(
                "ui/sidebar_visible", True, type=bool
            ),
            settings_visible=self.settings.value(
                "ui/settings_visible", True, type=bool
            ),
            logs_visible=self.settings.value(
                "ui/logs_visible", False, type=bool
            ),
            low_disk_warning_gb=low_disk_warning_gb,
            log_retention_days=log_retention_days,
        )

    def set_value(self, key, value):
        validators = {
            "startup/behavior": lambda item: item in {"recent", "blank"},
            "ui/accent": lambda item: item in SUPPORTED_ACCENTS,
            "window/restore_layout": lambda item: isinstance(item, bool),
            "editor/show_line_numbers": lambda item: isinstance(item, bool),
            "ui/sidebar_visible": lambda item: isinstance(item, bool),
            "ui/settings_visible": lambda item: isinstance(item, bool),
            "ui/logs_visible": lambda item: isinstance(item, bool),
            "storage/low_disk_warning_gb": (
                lambda item: 1 <= int(item) <= 1024
            ),
            "storage/log_retention_days": (
                lambda item: int(item) in {0, 1, 3, 7, 14, 30, 60, 90}
            ),
        }
        validator = validators.get(str(key))

        if validator is not None:
            try:
                valid = bool(validator(value))
            except (TypeError, ValueError):
                valid = False

            if not valid:
                raise SettingsError(f"Invalid value for {key}: {value}")

        self.settings.setValue(str(key), value)
        self.settings.sync()
        self.changed.emit(str(key), value)

    def set_library_root(self, path):
        path = Path(path).expanduser().resolve()
        self.settings.setValue("paths/library_root", str(path))
        self.settings.sync()
        self.paths = self._resolve_paths()
        self.paths.ensure_writable_folders()
        self.pathsChanged.emit(self.paths)

    def set_model_cache_root(self, path):
        path = Path(path).expanduser().resolve()
        self.settings.setValue("paths/model_cache_root", str(path))
        self.settings.sync()
        self.paths = self._resolve_paths()
        self.paths.ensure_writable_folders()
        self.pathsChanged.emit(self.paths)

    def reset_application_preferences(self):
        keys = (
            "startup/behavior",
            "window/restore_layout",
            "ui/accent",
            "editor/show_line_numbers",
            "ui/sidebar_visible",
            "ui/settings_visible",
            "ui/logs_visible",
            "storage/low_disk_warning_gb",
            "storage/log_retention_days",
            "window/layout_schema",
            "window/geometry",
            "window/state",
            "splitter/central",
            "splitter/scripts",
            "splitter/output",
            "splitter/segments",
        )

        for key in keys:
            self.settings.remove(key)

        self.settings.sync()
        self.resetRequested.emit()
