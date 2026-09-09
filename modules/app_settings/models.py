from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import uuid

from PySide6.QtCore import QObject, QSettings, Signal

APP_VERSION = "0.1.0-beta.1"
RELEASES_URL = "https://github.com/Candymanmax/MaxSpeech/releases/latest"
PREFERENCES_SCHEMA_VERSION = 1
LIBRARY_FOLDERS = ("input", "voices", "jobs", "final")
SUPPORTED_ACCENTS = (
    "rosewater",
    "flamingo",
    "pink",
    "mauve",
    "red",
    "maroon",
    "peach",
    "yellow",
    "green",
    "teal",
    "sky",
    "sapphire",
    "blue",
    "lavender",
)


class SettingsError(RuntimeError):
    """Raised when application settings cannot be applied safely."""


class PathMigrationError(SettingsError):
    """Raised when a library or model-cache copy cannot be completed."""


class CredentialStoreError(SettingsError):
    """Raised when the operating-system credential store is unavailable."""


@dataclass(frozen=True)
class AppPaths:
    """Resolved read-only and writable locations used by Diaphragm."""

    install_root: Path
    data_root: Path
    library_root: Path
    model_cache_root: Path
    defaults_file: Path
    config_file: Path
    logs_root: Path

    def __post_init__(self):
        for name in (
            "install_root",
            "data_root",
            "library_root",
            "model_cache_root",
            "defaults_file",
            "config_file",
            "logs_root",
        ):
            value = Path(getattr(self, name)).expanduser().resolve()
            object.__setattr__(self, name, value)

    @property
    def input_root(self):
        return self.library_root / "input"

    @property
    def voices_root(self):
        return self.library_root / "voices"

    @property
    def jobs_root(self):
        return self.library_root / "jobs"

    @property
    def outputs_root(self):
        return self.library_root / "final"

    @property
    def hub_cache_root(self):
        return self.model_cache_root / "huggingface" / "hub"

    @property
    def runtime_profiles_file(self):
        return self.model_cache_root / "runtime_profiles.json"

    def ensure_writable_folders(self):
        for folder in (
            self.data_root,
            self.input_root,
            self.voices_root,
            self.jobs_root,
            self.outputs_root,
            self.model_cache_root,
            self.logs_root,
        ):
            folder.mkdir(parents=True, exist_ok=True)

    def to_dict(self):
        return {
            name: str(getattr(self, name))
            for name in (
                "install_root",
                "data_root",
                "library_root",
                "model_cache_root",
                "defaults_file",
                "config_file",
                "logs_root",
            )
        }

    @classmethod
    def from_dict(cls, value):
        return cls(**dict(value))


@dataclass(frozen=True)
class AppPreferences:
    startup_behavior: str = "recent"
    restore_layout: bool = True
    accent: str = "teal"
    show_line_numbers: bool = True
    sidebar_visible: bool = True
    settings_visible: bool = True
    logs_visible: bool = False
    low_disk_warning_gb: int = 10
    log_retention_days: int = 14

    def __post_init__(self):
        if self.startup_behavior not in {"recent", "blank"}:
            raise ValueError("Startup behavior must be recent or blank")

        if self.accent not in SUPPORTED_ACCENTS:
            raise ValueError("Unsupported accent colour")

        for name in (
            "restore_layout",
            "show_line_numbers",
            "sidebar_visible",
            "settings_visible",
            "logs_visible",
        ):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be true or false")

        if not 1 <= int(self.low_disk_warning_gb) <= 1024:
            raise ValueError("Low-disk warning must be between 1 and 1024 GiB")

        if int(self.log_retention_days) not in {0, 1, 3, 7, 14, 30, 60, 90}:
            raise ValueError("Unsupported diagnostic-log retention period")
