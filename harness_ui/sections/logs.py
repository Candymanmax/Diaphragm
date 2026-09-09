"""Diagnostics dock workspace."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDockWidget,
    QHBoxLayout,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from harness_ui.icons import lucide_icon
from harness_ui.sections.base import CONTROL_SPACING, StatefulSection
from harness_ui.state import UiStateStore
from harness_ui.theme import BLUE, SECTION_SPACING, standard_button
from harness_ui.widgets import EmptyStateWidget


class LogsSection(StatefulSection):
    def __init__(self, state: UiStateStore, parent):
        super().__init__(state)
        self.logs_dock = QDockWidget("Logs and diagnostics", parent)
        self.logs_dock.setObjectName("LogsDock")
        self.logs_dock.setFeatures(
            QDockWidget.DockWidgetFeature.NoDockWidgetFeatures
        )
        self.logs_dock.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea
        )
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(SECTION_SPACING)
        self.logs_layout = layout
        toolbar = QHBoxLayout()
        toolbar.setSpacing(CONTROL_SPACING)
        self.log_filter = QComboBox()
        self.log_filter.addItems(("All events", "Errors only"))
        self.clear_logs_button = standard_button(
            "Clear",
            role="ghost",
            parent=panel,
        )
        self.copy_logs_button = standard_button(
            "Copy all",
            role="neutral",
            parent=panel,
        )
        toolbar.addWidget(self.log_filter)
        toolbar.addStretch(1)
        log_actions = QHBoxLayout()
        log_actions.setSpacing(CONTROL_SPACING)
        log_actions.addWidget(self.copy_logs_button)
        log_actions.addWidget(self.clear_logs_button)
        self.log_actions_layout = log_actions
        toolbar.addLayout(log_actions)
        layout.addLayout(toolbar)
        self.logs_stack = QStackedWidget()
        self.logs_empty_state = EmptyStateWidget(
            "No diagnostics yet",
            "Run a job to see generation activity and diagnostics here.",
            icon=lucide_icon("info", color=BLUE, size=24),
        )
        self.logs = QTextEdit()
        self.logs.setReadOnly(True)
        self.logs.document().setMaximumBlockCount(10000)
        self.logs.setAccessibleName("Generation logs and diagnostics")
        self.logs_stack.addWidget(self.logs_empty_state)
        self.logs_stack.addWidget(self.logs)
        self.logs_stack.setCurrentWidget(self.logs_empty_state)
        layout.addWidget(self.logs_stack)
        self.copy_logs_button.setEnabled(False)
        self.clear_logs_button.setEnabled(False)
        self.copy_logs_button.hide()
        self.clear_logs_button.hide()
        self.logs_dock.setWidget(panel)
        self.logs_dock.resize(parent.width(), 220)
        self.logs_dock.hide()


__all__ = ("LogsSection",)
