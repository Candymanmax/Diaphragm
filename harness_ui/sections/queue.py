"""Generation progress and queue workspace."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QStackedWidget,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

from harness_ui.icons import lucide_icon
from harness_ui.sections.base import CONTROL_SPACING, StatefulSection
from harness_ui.state import UiStateStore
from harness_ui.theme import SECTION_SPACING, SUBTEXT_0, standard_button
from harness_ui.widgets import EmptyStateWidget


class QueueTabSection(StatefulSection):
    def __init__(self, state: UiStateStore, parent=None):
        super().__init__(state)
        tab = QWidget(parent)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(SECTION_SPACING)
        controls = QHBoxLayout()
        controls.setSpacing(CONTROL_SPACING)
        self.runtime_label = QLabel("Runtime metrics appear after model load")
        self.runtime_label.setProperty("muted", True)
        self.pause_button = standard_button(
            "Pause",
            role="neutral",
            parent=tab,
        )
        self.cancel_button = standard_button(
            "Cancel",
            role="danger",
            parent=tab,
        )
        self.resume_button = standard_button(
            "Resume",
            role="primary",
            parent=tab,
        )
        self.retry_button = standard_button(
            "Retry failed",
            role="primary",
            parent=tab,
        )
        self.restart_button = standard_button(
            "Restart",
            role="neutral",
            parent=tab,
        )
        controls.addWidget(self.runtime_label, 1)
        queue_actions = QHBoxLayout()
        queue_actions.setSpacing(CONTROL_SPACING)
        queue_actions.addWidget(self.pause_button)
        queue_actions.addWidget(self.cancel_button)
        queue_actions.addWidget(self.resume_button)
        queue_actions.addWidget(self.retry_button)
        queue_actions.addWidget(self.restart_button)
        self.queue_actions_layout = queue_actions
        self.queue_action_buttons = (
            self.pause_button,
            self.cancel_button,
            self.resume_button,
            self.retry_button,
            self.restart_button,
        )
        for button in self.queue_action_buttons:
            button.hide()
        controls.addLayout(queue_actions)
        layout.addLayout(controls)

        self.queue_stack = QStackedWidget()
        self.queue_empty_state = EmptyStateWidget(
            "No active job",
            "Choose the scripts you want to process, then start generation.",
            "Go to scripts",
            icon=lucide_icon("arrow-right", color=SUBTEXT_0, size=24),
        )
        self.queue_empty_state.action_key = "scripts"
        self.queue_tree = QTreeWidget()
        self.queue_tree.setHeaderLabels((
            "Script / segment",
            "State",
            "Attempts",
            "Elapsed",
            "Details",
        ))
        self.queue_tree.setAlternatingRowColors(False)
        self.queue_tree.setAccessibleName("Job script and segment progress")
        self.queue_tree.header().setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )
        for column in (1, 2, 3):
            self.queue_tree.header().setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents,
            )
        self.queue_tree.header().setSectionResizeMode(
            4,
            QHeaderView.ResizeMode.Stretch,
        )
        self.queue_stack.addWidget(self.queue_empty_state)
        self.queue_stack.addWidget(self.queue_tree)
        self.queue_stack.setCurrentWidget(self.queue_empty_state)
        layout.addWidget(self.queue_stack, 1)

        self.widget = tab


__all__ = ("QueueTabSection",)
