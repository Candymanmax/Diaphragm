"""Persistent-job navigation sidebar."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
)

from harness_ui.icons import lucide_icon
from harness_ui.sections.base import StatefulSection
from harness_ui.state import UiStateStore
from harness_ui.theme import (
    COMPACT_SPACING,
    SECTION_SPACING,
    SUBTEXT_0,
    TEXT,
    icon_button,
    standard_button,
)
from harness_ui.widgets import EmptyStateWidget, JobListWidget


class JobsSidebarSection(StatefulSection):
    def __init__(self, state: UiStateStore, parent=None):
        super().__init__(state)
        sidebar = QFrame(parent)
        self.sidebar_panel = sidebar
        sidebar.setMinimumWidth(230)
        sidebar.setMaximumWidth(340)
        sidebar.setFrameShape(QFrame.Shape.NoFrame)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(SECTION_SPACING)

        heading_row = QHBoxLayout()
        heading_row.setSpacing(COMPACT_SPACING)
        heading = QLabel("Diaphragm")
        heading.setStyleSheet("font-size: 15pt; font-weight: 650;")
        self.search_jobs_button = icon_button(
            lucide_icon("search", color=SUBTEXT_0, size=18),
            role="ghost",
            parent=sidebar,
            icon_size=18,
            size=30,
            accessible_name="Search jobs and scripts",
            tool_tip="Search jobs and scripts",
        )
        self.refresh_jobs_button = icon_button(
            lucide_icon("refresh-cw", color=SUBTEXT_0, size=18),
            role="ghost",
            parent=sidebar,
            icon_size=18,
            size=30,
            accessible_name="Refresh jobs",
            tool_tip="Refresh jobs",
        )
        self.new_job_button = standard_button(
            "New job",
            role="ghost",
            parent=sidebar,
            object_name="newJobButton",
            icon=lucide_icon("plus", color=TEXT, size=16),
            variant="navigation",
            accessible_name="Create a new TTS job",
        )
        self.new_job_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        heading_row.addWidget(heading)
        heading_row.addStretch(1)
        heading_row.addWidget(self.search_jobs_button)
        heading_row.addWidget(self.refresh_jobs_button)
        layout.addLayout(heading_row)

        new_job_row = QHBoxLayout()
        new_job_row.setSpacing(COMPACT_SPACING)
        new_job_row.addWidget(self.new_job_button)
        layout.addLayout(new_job_row)

        self.jobs_button = standard_button(
            "Jobs",
            role="ghost",
            parent=sidebar,
            object_name="jobsButton",
            icon=lucide_icon("list", color=TEXT, size=16),
            variant="navigation",
            accessible_name="Show active jobs",
            tool_tip="Show active jobs",
        )
        self.jobs_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        jobs_row = QHBoxLayout()
        jobs_row.setSpacing(COMPACT_SPACING)
        jobs_row.addWidget(self.jobs_button)
        layout.addLayout(jobs_row)

        self.archived_jobs_button = standard_button(
            "Archived",
            role="ghost",
            parent=sidebar,
            object_name="archivedJobsButton",
            icon=lucide_icon("archive", color=TEXT, size=16),
            variant="navigation",
            accessible_name="Show archived jobs",
            tool_tip="Show archived jobs",
        )
        self.archived_jobs_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        archive_row = QHBoxLayout()
        archive_row.setSpacing(COMPACT_SPACING)
        archive_row.addWidget(self.archived_jobs_button)
        layout.addLayout(archive_row)

        self.job_list = JobListWidget()
        self.job_list.setObjectName("jobList")
        self.job_list.setSpacing(COMPACT_SPACING)
        self.job_list.setAccessibleName("Persistent TTS jobs")
        self.job_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.job_list_stack = QStackedWidget()
        self.job_list_stack.setObjectName("jobListStack")
        self.job_list_stack.addWidget(self.job_list)
        self.jobs_empty_state = EmptyStateWidget(
            "No jobs yet",
            "Create a job to start generating audio.",
            "New job",
            icon=lucide_icon("list", color=SUBTEXT_0, size=24),
            action_role="primary",
        )
        self.job_list_stack.addWidget(self.jobs_empty_state)
        self.job_list_stack.setCurrentWidget(self.jobs_empty_state)
        layout.addWidget(self.job_list_stack, 1)

        self.widget = sidebar

    def set_empty_state(self, empty, *, archived=False):
        """Show a contextual empty state without replacing the job list."""

        if not empty:
            self.job_list_stack.setCurrentWidget(self.job_list)
            return

        if archived:
            title = "No archived jobs"
            message = "Archived jobs will appear here when you archive one."
            action_text = "Show active jobs"
            action_key = "show_active_jobs"
        else:
            title = "No jobs yet"
            message = "Create a job to start generating audio."
            action_text = "New job"
            action_key = "new_job"

        self.jobs_empty_state.set_state(
            title,
            message,
            action_text,
            icon=lucide_icon("list", color=SUBTEXT_0, size=24),
            action_key=action_key,
        )
        self.job_list_stack.setCurrentWidget(self.jobs_empty_state)


__all__ = ("JobsSidebarSection",)
