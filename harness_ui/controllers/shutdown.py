"""Application shutdown policy and resource cleanup."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from harness_ui.dialogs import AppDialog, UnsavedScriptDialog
from harness_ui.state import UiStateStore
from harness_ui.theme import YELLOW
from modules.jobs import JobStoreError


@dataclass(frozen=True)
class ShutdownSnapshot:
    """Immutable state relevant to a close request."""

    preferences_open: bool
    preferences_operation_active: bool
    unsaved_script: bool
    generation_running: bool


class ShutdownController(QObject):
    """Coordinate guarded application exit without owning window widgets."""

    snapshotChanged = Signal(object)

    def __init__(
        self,
        *,
        parent,
        state: UiStateStore,
        service,
        worker,
        script_controller,
        output_controller,
        appearance_controller,
        focus_preferences=None,
        confirm_unsaved=None,
        confirm_generation=None,
        status_message=None,
    ):
        super().__init__(parent)
        self.parent_window = parent
        self.state = state
        self.service = service
        self.worker = worker
        self.script_controller = script_controller
        self.output_controller = output_controller
        self.appearance_controller = appearance_controller
        self._focus_preferences = focus_preferences or (lambda: None)
        self._confirm_unsaved = confirm_unsaved or UnsavedScriptDialog.confirm
        self._confirm_generation = (
            confirm_generation or self._confirm_running_generation
        )
        self._status_message = status_message or (lambda _message, _timeout: None)

    def _confirm_running_generation(self, parent, title, message):
        return AppDialog.confirm(
            parent,
            title,
            message,
            confirm_text="Pause and exit",
            cancel_text="Keep running",
            default_action="secondary",
            icon_name="triangle-alert",
            icon_color=YELLOW,
        )

    def snapshot(self):
        preferences = self.state.get("preferences_dialog")
        return ShutdownSnapshot(
            preferences_open=preferences is not None,
            preferences_operation_active=bool(
                preferences is not None and preferences.migration_active
            ),
            unsaved_script=self.script_controller.exit_requires_confirmation(),
            generation_running=bool(self.worker.running),
        )

    def _publish_snapshot(self):
        self.snapshotChanged.emit(self.snapshot())

    def confirm_unsaved_exit(self):
        return self._confirm_unsaved(self.parent_window)

    def request_close(self, event):
        """Accept or reject a main-window close event after safety checks."""

        preferences = self.state.get("preferences_dialog")

        if preferences is not None:
            if not preferences.prepare_for_application_exit():
                self._focus_preferences()
                self._status_message(
                    "Wait for the active Preferences operation to finish",
                    5000,
                )
                event.ignore()
                self._publish_snapshot()
                return

        if self.script_controller.exit_requires_confirmation():
            if not self.confirm_unsaved_exit():
                event.ignore()
                self._publish_snapshot()
                return

        if self.worker.running:
            confirmed = self._confirm_generation(
                self.parent_window,
                "Generation is still running",
                "Pause the job and exit? The active inference may be "
                "interrupted, but completed segment files will be preserved.",
            )

            if not confirmed:
                event.ignore()
                self._publish_snapshot()
                return

            job_id = self.state.get("current_job_id")

            try:
                if job_id:
                    self.service.request_pause(job_id)
            except (JobStoreError, OSError):
                pass

            self.worker.terminate()

            if job_id:
                try:
                    manifest = self.service.load_job(job_id)
                    self.service.store.recover(manifest)
                except (JobStoreError, OSError):
                    pass

        self.output_controller.release_media_source()
        self.worker.close()
        self.appearance_controller.save_window_state()
        event.accept()
        self._publish_snapshot()


__all__ = ("ShutdownController", "ShutdownSnapshot")
