"""Active-job header, progress, completion, and workspace tabs."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from harness_ui.icons import lucide_icon
from harness_ui.sections.base import CONTROL_SPACING, StatefulSection
from harness_ui.state import UiStateStore
from harness_ui.theme import (
    GREEN,
    PAGE_SPACING,
    SECTION_SPACING,
    SUBTEXT_0,
    TIGHT_SPACING,
    icon_button,
    standard_button,
)


class JobHeaderSection(StatefulSection):
    """Own the active-job summary and its three work tabs."""

    def __init__(
        self,
        state: UiStateStore,
        scripts_widget,
        queue_widget,
        output_widget,
        parent=None,
    ):
        super().__init__(state)
        self.widget = QWidget(parent)
        layout = QVBoxLayout(self.widget)
        layout.setContentsMargins(18, 14, 18, 12)
        layout.setSpacing(PAGE_SPACING)
        self.layout = layout

        header = QHBoxLayout()
        header.setSpacing(CONTROL_SPACING)
        self.job_title = QLabel("New TTS job")
        self.job_title.setObjectName("jobHeaderTitle")
        self.job_title.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        header.addWidget(self.job_title, 1)
        self.job_segment_count = QLabel("No segments")
        self.job_segment_count.setObjectName("jobSegmentCount")
        self.job_segment_count.setProperty("muted", True)
        header.addWidget(self.job_segment_count)
        self.job_header_action = standard_button(
            "Run job",
            role="primary",
            parent=self.widget,
            object_name="jobHeaderAction",
        )
        self.state.set("job_header_action_mode", "run")
        header.addWidget(self.job_header_action)
        action_height = self.job_header_action.sizeHint().height()
        self.settings_toggle_button = icon_button(
            lucide_icon("settings", color=SUBTEXT_0, size=17),
            role="neutral",
            parent=self.widget,
            object_name="settingsToggleButton",
            icon_size=17,
            size=action_height,
            accessible_name="Hide job settings inspector",
            tool_tip="Hide job settings inspector",
            auto_raise=False,
        )
        header.addWidget(self.settings_toggle_button)
        layout.addLayout(header)

        self.progress_panel = QWidget()
        progress_row = QHBoxLayout(self.progress_panel)
        progress_row.setContentsMargins(0, 0, 0, 0)
        progress_row.setSpacing(CONTROL_SPACING)
        self.job_progress = QProgressBar()
        self.job_progress.setRange(0, 100)
        self.job_progress.setValue(0)
        self.job_progress.setTextVisible(False)
        self.progress_text = QLabel("No active job")
        self.progress_text.setProperty("muted", True)
        progress_row.addWidget(self.job_progress, 1)
        progress_row.addWidget(self.progress_text)
        self.progress_panel.hide()
        layout.addWidget(self.progress_panel)

        self.completion_panel = QFrame()
        self.completion_panel.setObjectName("completionSummary")
        completion_layout = QHBoxLayout(self.completion_panel)
        completion_layout.setContentsMargins(14, 9, 10, 9)
        completion_layout.setSpacing(SECTION_SPACING)
        self.completion_mark = QLabel()
        self.completion_mark.setObjectName("completionMark")
        self.completion_mark.setPixmap(
            lucide_icon("check", color=GREEN, size=24).pixmap(24, 24)
        )
        self.completion_mark.setAccessibleName("Generation complete")
        completion_copy = QVBoxLayout()
        completion_copy.setSpacing(TIGHT_SPACING)
        self.completion_title = QLabel("Generation complete")
        self.completion_title.setObjectName("completionTitle")
        self.completion_text = QLabel("Generation complete")
        self.completion_text.setObjectName("completionText")
        completion_layout.addWidget(self.completion_mark)
        completion_copy.addWidget(self.completion_title)
        completion_copy.addWidget(self.completion_text)
        completion_layout.addLayout(completion_copy, 1)
        self.completion_review_button = standard_button(
            "Review output",
            role="neutral",
            parent=self.completion_panel,
        )
        self.completion_new_job_button = standard_button(
            "New job",
            role="primary",
            parent=self.completion_panel,
        )
        completion_layout.addWidget(self.completion_review_button)
        completion_layout.addWidget(self.completion_new_job_button)
        self.completion_panel.hide()
        layout.addWidget(self.completion_panel)

        self.error_banner = QLabel()
        self.error_banner.setProperty("error", True)
        self.error_banner.setWordWrap(True)
        self.error_banner.hide()
        layout.addWidget(self.error_banner)

        self.work_tabs = QTabWidget()
        self.work_tabs.setObjectName("workTabs")
        self.work_tabs.setDocumentMode(True)
        self.work_tabs.addTab(scripts_widget, "Scripts")
        self.work_tabs.addTab(queue_widget, "Job progress")
        self.work_tabs.addTab(output_widget, "Review output")
        layout.addWidget(self.work_tabs, 1)


__all__ = ("JobHeaderSection",)
