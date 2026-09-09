"""Diagnostics state and rendering for the desktop interface."""

from __future__ import annotations

from dataclasses import dataclass
import html

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from harness_ui.icons import lucide_icon
from harness_ui.state import UiStateStore
from harness_ui.theme import BLUE, GREEN, OVERLAY_0, RED, TEXT, YELLOW


@dataclass(frozen=True)
class DiagnosticsSnapshot:
    """Immutable summary of the diagnostics currently held in memory."""

    total_entries: int
    error_entries: int
    errors_only: bool


class DiagnosticsController(QObject):
    """Own log retention in UI state and render the diagnostics section."""

    snapshotChanged = Signal(object)

    def __init__(self, *, parent, view, state: UiStateStore, log_store):
        super().__init__(parent)
        self.view = view
        self.state = state
        self.log_store = log_store
        self.state.diagnosticsChanged.connect(self._state_changed)

    def _state_changed(self, field_name, _previous, _value):
        if field_name == "log_filter":
            self.render()

    @property
    def entries(self):
        return self.state.get("log_entries")

    @entries.setter
    def entries(self, value):
        self.state.set("log_entries", list(value))

    def snapshot(self):
        entries = self.entries
        return DiagnosticsSnapshot(
            total_entries=len(entries),
            error_entries=sum(entry[1] == "error" for entry in entries),
            errors_only=self.state.get("log_filter") == "Errors only",
        )

    def _publish_snapshot(self):
        self.snapshotChanged.emit(self.snapshot())

    def append(self, message, level="info", timestamp=None):
        entry = (str(message), str(level), timestamp)
        entries = [*self.entries, entry]

        if len(entries) > 10000:
            entries = entries[-10000:]

        self.entries = entries

        try:
            self.log_store.write(level, message, timestamp)
        except OSError:
            pass

        errors_only = self.state.get("log_filter") == "Errors only"
        self.view.copy_logs_button.setEnabled(True)
        self.view.clear_logs_button.setEnabled(True)
        self.view.copy_logs_button.show()
        self.view.clear_logs_button.show()

        if errors_only and level != "error":
            if not any(value[1] == "error" for value in self.entries):
                self.show_empty(errors_only=True)
            self._publish_snapshot()
            return

        self.view.logs_stack.setCurrentWidget(self.view.logs)
        self._append_entry(entry)
        self._publish_snapshot()

    def _append_entry(self, entry):
        message, level, timestamp = entry
        color = {
            "error": RED,
            "warning": YELLOW,
            "info": TEXT,
        }.get(level, TEXT)
        stamp = (timestamp or "").split("T")[-1].replace("+00:00", "")
        prefix = f"{stamp[:12]} " if stamp else ""
        safe = html.escape(str(message))
        self.view.logs.append(
            f'<span style="color:{OVERLAY_0}">{prefix}</span>'
            f'<span style="color:{color}">{safe}</span>'
        )

    def render(self, *args):
        del args
        filter_name = str(self.state.get("log_filter") or "All events")
        if filter_name not in {"All events", "Errors only"}:
            filter_name = "All events"
        if self.view.log_filter.currentText() != filter_name:
            self.view.log_filter.blockSignals(True)
            self.view.log_filter.setCurrentText(filter_name)
            self.view.log_filter.blockSignals(False)
        errors_only = filter_name == "Errors only"
        self.view.logs.clear()
        visible_entries = [
            entry
            for entry in self.entries
            if not errors_only or entry[1] == "error"
        ]

        for entry in visible_entries:
            self._append_entry(entry)

        if visible_entries:
            self.view.logs_stack.setCurrentWidget(self.view.logs)
        else:
            self.show_empty(errors_only=errors_only)

        has_entries = bool(self.entries)
        self.view.copy_logs_button.setEnabled(has_entries)
        self.view.clear_logs_button.setEnabled(has_entries)
        self.view.copy_logs_button.setVisible(has_entries)
        self.view.clear_logs_button.setVisible(has_entries)
        self._publish_snapshot()

    def set_filter(self, value):
        """Commit the selected diagnostics filter, then render it."""

        value = str(value)
        if value not in {"All events", "Errors only"}:
            value = "All events"
        self.state.set("log_filter", value)

    def show_all_events(self):
        self.set_filter("All events")

    def show_empty(self, *, errors_only=False):
        if errors_only and self.entries:
            self.view.logs_empty_state.set_state(
                "No errors found",
                "Nothing needs attention in the current diagnostics.",
                "Show all events",
                icon=lucide_icon("check", color=GREEN, size=24),
                action_key="all_logs",
            )
        else:
            self.view.logs_empty_state.set_state(
                "No diagnostics yet",
                "Run a job to see generation activity and diagnostics here.",
                icon=lucide_icon("info", color=BLUE, size=24),
            )

        self.view.logs_stack.setCurrentWidget(self.view.logs_empty_state)

    def clear(self):
        self.entries = []
        self.render()

    def copy(self):
        lines = []

        for message, level, timestamp in self.entries:
            stamp = (timestamp or "").split("T")[-1].replace("+00:00", "")
            prefix = f"{stamp[:12]} " if stamp else ""
            lines.append(f"{prefix}[{level.upper()}] {message}")

        QApplication.clipboard().setText("\n".join(lines))
