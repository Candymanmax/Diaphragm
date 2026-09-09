"""Preferences-window lifecycle and preference-to-workspace synchronization."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal
from harness_ui.dialogs import AppDialog
from harness_ui.preferences import PreferencesDialog
from harness_ui.state import UiStateStore


@dataclass(frozen=True)
class PreferencesSnapshot:
    """Immutable Preferences-window lifecycle state."""

    visible: bool
    migration_active: bool


class PreferencesController(QObject):
    """Open one Preferences window and synchronize committed changes."""

    snapshotChanged = Signal(object)
    modelRefreshRequested = Signal()

    def __init__(
        self,
        *,
        parent,
        state: UiStateStore,
        settings_repository,
        service,
        log_store,
        worker,
        model_busy,
        settings_model_controller,
        script_controller,
        set_accent,
        set_sidebar_visible,
        set_dock_visible,
        reset_window_layout,
        status_message,
    ):
        super().__init__(parent)
        self.parent_window = parent
        self.state = state
        self.settings_repository = settings_repository
        self.service = service
        self.log_store = log_store
        self.worker = worker
        self._model_busy = model_busy
        self._settings_model_controller = settings_model_controller
        self._settings_model_controller.statusChanged.connect(
            lambda *_: self.refresh_models()
        )
        self.script_controller = script_controller
        self._set_accent = set_accent
        self._set_sidebar_visible = set_sidebar_visible
        self._set_dock_visible = set_dock_visible
        self._reset_window_layout = reset_window_layout
        self._status_message = status_message

    def _dialog(self):
        return self.state.get("preferences_dialog")

    def _set_dialog(self, dialog):
        self.state.set("preferences_dialog", dialog)

    def focus(self):
        """Bring the existing Preferences window to the foreground."""

        dialog = self._dialog()
        if dialog is None:
            return
        self.refresh_models()
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        self._publish_snapshot()

    def snapshot(self):
        dialog = self._dialog()
        return PreferencesSnapshot(
            visible=bool(dialog is not None and dialog.isVisible()),
            migration_active=bool(
                dialog is not None and dialog.migration_active
            ),
        )

    def _publish_snapshot(self):
        self.snapshotChanged.emit(self.snapshot())

    def refresh_models(self):
        """Refresh an open Preferences model page from shared cache state."""

        dialog = self._dialog()
        if dialog is None or dialog.model_manager.busy:
            return

        dialog.model_manager.refresh_inventory()

    def show(self):
        dialog = self._dialog()

        if dialog is not None:
            if not dialog.model_manager.busy:
                dialog.model_manager.refresh_inventory()
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()
            self._publish_snapshot()
            return

        dialog = PreferencesDialog(
            self.settings_repository,
            self.service,
            log_store=self.log_store,
            worker_running=lambda: self.worker.running,
            model_busy=self._model_busy,
            parent=self.parent_window,
        )
        self._set_dialog(dialog)
        dialog.accentChanged.connect(
            lambda name: self._set_accent(name, persist=False)
        )
        dialog.lineNumbersChanged.connect(
            lambda visible: self.script_controller.set_line_numbers(
                visible,
                persist=False,
            )
        )
        dialog.panelVisibilityChanged.connect(self.panel_visibility_changed)
        dialog.layoutResetRequested.connect(self._reset_window_layout)
        dialog.restartRequired.connect(self.restart_requested)
        dialog.modelsChanged.connect(self.modelRefreshRequested.emit)
        dialog.model_manager.operationStateChanged.connect(
            self._settings_model_controller.set_external_busy
        )
        dialog.finished.connect(self.closed)
        AppDialog.center_on_window(dialog, self.parent_window)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        self._publish_snapshot()

    def closed(self, _result):
        self._set_dialog(None)
        self._publish_snapshot()

    def panel_visibility_changed(self, panel, visible):
        if panel == "sidebar":
            self._set_sidebar_visible(visible, persist=False)
        elif panel == "settings":
            self._set_dock_visible(
                "settings",
                visible,
                persist=False,
            )
        elif panel == "logs":
            self._set_dock_visible(
                "logs",
                visible,
                persist=False,
            )

    def config_saved(self, _config):
        self._status_message(
            "Job settings saved as defaults",
            4000,
        )

    def restart_requested(self, kind):
        label = "personal library" if kind == "library" else "model cache"
        if AppDialog.confirm(
            self.parent_window,
            "Restart required",
            f"The {label} was copied and selected successfully. Exit "
            "Diaphragm now, then reopen it to use the new location?",
            confirm_text="Exit and restart",
            cancel_text="Later",
            default_action="secondary",
        ):
            self.parent_window.close()


__all__ = ("PreferencesController", "PreferencesSnapshot")
