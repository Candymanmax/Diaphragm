"""Central state for the desktop harness.

The main window historically kept this information as a collection of
unrelated attributes.  ``UiStateStore`` gives components one typed source of
truth while retaining signal names that are intentionally small and generic.
The store does not perform UI work; consumers decide how a state transition
should be rendered.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Signal


@dataclass
class UiState:
    """Mutable application state shared by the main-window components."""

    accent_name: str = "teal"
    current_script_path: Path | None = None
    script_loading: bool = False
    script_dirty: bool = False
    current_manifest: dict[str, Any] | None = None
    current_job_id: str | None = None
    temporary_jobs: dict[str, dict[str, Any]] = field(default_factory=dict)
    showing_archived_jobs: bool = False
    current_segment: tuple[str, dict[str, Any]] | None = None
    manifest_updated_at: str | None = None
    worker_finished_handled: bool = True
    worker_return_code: int | None = None
    runtime_summary: str = "Runtime metrics appear after model load"
    pause_requested: bool = False
    cancel_requested: bool = False
    workspace_error_message: str | None = None
    last_job_refresh: float = 0.0
    log_entries: list[tuple[Any, ...]] = field(default_factory=list)
    log_filter: str = "All events"
    job_search_dialog: QObject | None = None
    preferences_dialog: QObject | None = None
    job_header_action_mode: str = "run"
    sidebar_visible: bool = True
    settings_visible: bool = True
    logs_visible: bool = False
    line_numbers_visible: bool = True
    active_tab: int = 0


class UiStateStore(QObject):
    """Own and publish application state without coupling it to widgets.

    ``stateChanged`` is emitted only after a value changes and includes the
    field name, previous value, and new value.  The narrower signals are
    useful to components that should not react to unrelated transitions.
    """

    stateChanged = Signal(str, object, object)
    scriptChanged = Signal(object, object)
    jobChanged = Signal(object, object)
    workerChanged = Signal(object, object)
    generationChanged = Signal(str, object, object)
    feedbackChanged = Signal(object, object)
    diagnosticsChanged = Signal(str, object, object)
    dialogChanged = Signal(str, object, object)
    panelChanged = Signal(str, object, object)

    _SCRIPT_FIELDS = frozenset(
        {"current_script_path", "script_loading", "script_dirty"}
    )
    _JOB_FIELDS = frozenset(
        {
            "current_manifest",
            "current_job_id",
            "temporary_jobs",
            "showing_archived_jobs",
            "current_segment",
            "manifest_updated_at",
            "last_job_refresh",
            "job_header_action_mode",
        }
    )
    _PANEL_FIELDS = frozenset(
        {
            "sidebar_visible",
            "settings_visible",
            "logs_visible",
            "line_numbers_visible",
            "active_tab",
        }
    )
    _WORKER_FIELDS = frozenset(
        {
            "worker_finished_handled",
            "worker_return_code",
            "runtime_summary",
            "pause_requested",
            "cancel_requested",
        }
    )
    _FEEDBACK_FIELDS = frozenset({"workspace_error_message"})
    _DIAGNOSTIC_FIELDS = frozenset({"log_filter"})
    _DIALOG_FIELDS = frozenset(
        {"job_search_dialog", "preferences_dialog"}
    )

    def __init__(self, parent: QObject | None = None, state: UiState | None = None):
        super().__init__(parent)
        self.state = state or UiState()

    def get(self, field_name: str) -> Any:
        return getattr(self.state, field_name)

    def set(self, field_name: str, value: Any) -> bool:
        """Set one field and emit the appropriate transition signals."""

        previous = getattr(self.state, field_name)

        if previous == value:
            return False

        setattr(self.state, field_name, value)
        self.stateChanged.emit(field_name, previous, value)

        if field_name in self._SCRIPT_FIELDS:
            self.scriptChanged.emit(previous, value)
        elif field_name in self._JOB_FIELDS:
            self.jobChanged.emit(previous, value)
        elif field_name in self._WORKER_FIELDS:
            self.workerChanged.emit(previous, value)
            self.generationChanged.emit(field_name, previous, value)
        elif field_name in self._FEEDBACK_FIELDS:
            self.feedbackChanged.emit(previous, value)
        elif field_name in self._DIAGNOSTIC_FIELDS:
            self.diagnosticsChanged.emit(field_name, previous, value)
        elif field_name in self._DIALOG_FIELDS:
            self.dialogChanged.emit(field_name, previous, value)
        elif field_name in self._PANEL_FIELDS:
            self.panelChanged.emit(field_name, previous, value)

        return True

    def update(self, **values: Any) -> None:
        """Apply several fields in declaration order."""

        for field_name, value in values.items():
            self.set(field_name, value)
