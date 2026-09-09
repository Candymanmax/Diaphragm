"""Immediate-persistence behavior for ordinary application preferences."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from harness_ui.dialogs import AppDialog
from harness_ui.preferences.common import open_folder, set_feedback
from modules.app_settings import RELEASES_URL


@dataclass(frozen=True)
class PreferenceValuesSnapshot:
    """Immutable application preference values shown by the dialog."""

    startup_behavior: str
    restore_layout: bool
    accent: str
    show_line_numbers: bool
    sidebar_visible: bool
    settings_visible: bool
    logs_visible: bool
    low_disk_warning_gb: int
    log_retention_days: int


class PreferenceValuesController(QObject):
    """Load and immediately persist non-destructive preference controls."""

    snapshotChanged = Signal(object)

    def __init__(
        self,
        *,
        dialog,
        repository,
        log_store,
        refresh_paths,
        refresh_credentials,
    ):
        super().__init__(dialog)
        self.dialog = dialog
        self.repository = repository
        self.log_store = log_store
        self._refresh_paths = refresh_paths
        self._refresh_credentials = refresh_credentials

    def snapshot(self):
        preferences = self.repository.preferences()
        return PreferenceValuesSnapshot(
            startup_behavior=preferences.startup_behavior,
            restore_layout=preferences.restore_layout,
            accent=preferences.accent,
            show_line_numbers=preferences.show_line_numbers,
            sidebar_visible=preferences.sidebar_visible,
            settings_visible=preferences.settings_visible,
            logs_visible=preferences.logs_visible,
            low_disk_warning_gb=preferences.low_disk_warning_gb,
            log_retention_days=preferences.log_retention_days,
        )

    def _publish_snapshot(self):
        self.snapshotChanged.emit(self.snapshot())

    def load(self):
        dialog = self.dialog
        preferences = self.repository.preferences()
        dialog.startup_behavior.setCurrentIndex(
            max(
                0,
                dialog.startup_behavior.findData(
                    preferences.startup_behavior
                ),
            )
        )
        dialog.restore_layout.setChecked(preferences.restore_layout)
        dialog.accent.setCurrentIndex(
            max(0, dialog.accent.findData(preferences.accent))
        )
        dialog.show_line_numbers.setChecked(preferences.show_line_numbers)
        dialog.show_sidebar.setChecked(preferences.sidebar_visible)
        dialog.show_settings.setChecked(preferences.settings_visible)
        dialog.show_logs.setChecked(preferences.logs_visible)
        dialog.low_disk_warning.setValue(preferences.low_disk_warning_gb)
        dialog.log_retention.setCurrentIndex(
            max(
                0,
                dialog.log_retention.findData(
                    preferences.log_retention_days
                ),
            )
        )
        self._refresh_paths()
        self._refresh_credentials()
        self._publish_snapshot()

    def connect(self):
        dialog = self.dialog
        dialog.navigation.currentRowChanged.connect(
            dialog.pages.setCurrentIndex
        )
        dialog.startup_behavior.currentIndexChanged.connect(
            lambda _index: self._set_value(
                "startup/behavior",
                dialog.startup_behavior.currentData(),
            )
        )
        dialog.restore_layout.toggled.connect(
            lambda checked: self._set_value(
                "window/restore_layout",
                checked,
            )
        )
        dialog.accent.currentIndexChanged.connect(self.accent_changed)
        dialog.show_line_numbers.toggled.connect(self.line_numbers_changed)
        dialog.show_sidebar.toggled.connect(
            lambda checked: self.panel_changed("sidebar", checked)
        )
        dialog.show_settings.toggled.connect(
            lambda checked: self.panel_changed("settings", checked)
        )
        dialog.show_logs.toggled.connect(
            lambda checked: self.panel_changed("logs", checked)
        )
        dialog.reset_layout_button.clicked.connect(
            dialog.layoutResetRequested
        )
        dialog.open_app_data_button.clicked.connect(
            lambda: open_folder(self.repository.paths.data_root)
        )
        dialog.reset_preferences_button.clicked.connect(self.reset)
        dialog.low_disk_warning.valueChanged.connect(
            lambda value: self._set_value(
                "storage/low_disk_warning_gb",
                value,
            )
        )
        dialog.log_retention.currentIndexChanged.connect(
            self.log_retention_changed
        )
        dialog.open_releases_button.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(RELEASES_URL))
        )

    def _set_value(self, key, value):
        self.repository.set_value(key, value)
        self._publish_snapshot()

    def accent_changed(self, *args):
        del args
        name = str(self.dialog.accent.currentData() or "teal")
        self.repository.set_value("ui/accent", name)
        self.dialog.accentChanged.emit(name)
        self._publish_snapshot()

    def line_numbers_changed(self, checked):
        self.repository.set_value(
            "editor/show_line_numbers",
            bool(checked),
        )
        self.dialog.lineNumbersChanged.emit(bool(checked))
        self._publish_snapshot()

    def panel_changed(self, panel, checked):
        key = {
            "sidebar": "ui/sidebar_visible",
            "settings": "ui/settings_visible",
            "logs": "ui/logs_visible",
        }[panel]
        self.repository.set_value(key, bool(checked))
        self.dialog.panelVisibilityChanged.emit(panel, bool(checked))
        self._publish_snapshot()

    def log_retention_changed(self, *args):
        del args
        days = int(self.dialog.log_retention.currentData())
        self.repository.set_value("storage/log_retention_days", days)
        self.log_store.retention_days = days
        self.log_store.prune(days)
        self._publish_snapshot()

    def reset(self):
        if not AppDialog.confirm(
            self.dialog,
            "Reset preferences",
            "Reset interface, startup, and storage preferences?\n\n"
            "Scripts, voices, jobs, models, outputs, and credentials are kept.",
            confirm_text="Reset preferences",
            cancel_text="Cancel",
            confirm_role="danger",
            default_action="secondary",
        ):
            return

        self.repository.reset_application_preferences()
        self.load()
        self.dialog.layoutResetRequested.emit()
        set_feedback(
            self.dialog.general_feedback,
            "Application preferences reset.",
        )


__all__ = ("PreferenceValuesController", "PreferenceValuesSnapshot")
