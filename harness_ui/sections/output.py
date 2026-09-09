"""Generated-audio playback and retained-segment review workspace."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QPlainTextEdit,
    QSlider,
    QStackedWidget,
    QSplitter,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from harness_ui.icons import lucide_icon
from harness_ui.sections.base import CONTROL_SPACING, StatefulSection
from harness_ui.state import UiStateStore
from harness_ui.theme import (
    CONTROL_SPACING,
    INLINE_SPACING,
    SECTION_SPACING,
    SUBTEXT_0,
    TEXT,
    standard_button,
)
from harness_ui.widgets import EmptyStateWidget, WaveformWidget


class OutputTabSection(StatefulSection):
    def __init__(self, state: UiStateStore, parent=None):
        super().__init__(state)
        tab = QWidget(parent)
        outer = QVBoxLayout(tab)
        outer.setContentsMargins(0, 10, 0, 0)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)

        player_panel = QWidget()
        player_layout = QVBoxLayout(player_panel)
        player_layout.setContentsMargins(0, 0, 0, 6)
        player_layout.setSpacing(SECTION_SPACING)
        output_header = QHBoxLayout()
        output_header.setSpacing(CONTROL_SPACING)
        output_header.addWidget(QLabel("Generated outputs"))
        output_header.addStretch(1)
        self.open_output_button = standard_button(
            "Open file",
            role="neutral",
            parent=player_panel,
        )
        self.open_output_folder_button = standard_button(
            "Open output folder",
            role="neutral",
            parent=player_panel,
        )
        output_actions = QHBoxLayout()
        output_actions.setSpacing(CONTROL_SPACING)
        output_actions.addWidget(self.open_output_button)
        output_actions.addWidget(self.open_output_folder_button)
        self.output_actions_layout = output_actions
        self.output_action_buttons = (
            self.open_output_button,
            self.open_output_folder_button,
        )
        for button in self.output_action_buttons:
            button.hide()
        output_header.addLayout(output_actions)
        player_layout.addLayout(output_header)

        self.output_stack = QStackedWidget()
        self.output_empty_state = EmptyStateWidget(
            "No output yet",
            "Run a job, then return here to preview the generated audio.",
            "Go to scripts",
            icon=lucide_icon("music-2", color=SUBTEXT_0, size=24),
        )
        self.output_empty_state.action_key = "scripts"
        output_content = QWidget()
        output_content_layout = QVBoxLayout(output_content)
        output_content_layout.setContentsMargins(0, 0, 0, 0)
        output_content_layout.setSpacing(INLINE_SPACING)
        self.output_list = QListWidget()
        self.output_list.setMaximumHeight(120)
        self.output_list.setAccessibleName("Generated output files")
        output_content_layout.addWidget(self.output_list)
        self.output_metadata = QLabel("Select an output to preview it")
        self.output_metadata.setProperty("muted", True)
        output_content_layout.addWidget(self.output_metadata)
        self.waveform = WaveformWidget()
        output_content_layout.addWidget(self.waveform)
        playback = QHBoxLayout()
        playback.setSpacing(CONTROL_SPACING)
        self.play_button = standard_button(
            role="neutral",
            parent=output_content,
            object_name="audioPlayButton",
            icon=lucide_icon("play", color=TEXT, size=17),
            icon_size=17,
            accessible_name="Play audio",
        )
        self.play_button.setFixedSize(34, 30)
        self.play_button.setEnabled(False)
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 1000)
        self.position_slider.setAccessibleName("Audio playback position")
        self.position_text = QLabel("0:00 / 0:00")
        playback.addWidget(self.play_button)
        playback.addWidget(self.position_slider, 1)
        playback.addWidget(self.position_text)
        output_content_layout.addLayout(playback)
        self.output_stack.addWidget(self.output_empty_state)
        self.output_stack.addWidget(output_content)
        self.output_stack.setCurrentWidget(self.output_empty_state)
        self.output_content = output_content
        player_layout.addWidget(self.output_stack, 1)
        splitter.addWidget(player_panel)

        segment_panel = QWidget()
        segment_layout = QVBoxLayout(segment_panel)
        segment_layout.setContentsMargins(0, 6, 0, 0)
        segment_layout.setSpacing(SECTION_SPACING)
        segment_header = QHBoxLayout()
        segment_header.setSpacing(CONTROL_SPACING)
        segment_header.addWidget(QLabel("Segments"))
        self.segment_hint = QLabel(
            "Enable segment retention before running to edit or regenerate."
        )
        self.segment_hint.setProperty("muted", True)
        segment_header.addWidget(self.segment_hint, 1)
        self.play_segment_button = standard_button(
            "Play segment",
            role="neutral",
            parent=segment_panel,
        )
        self.save_segment_button = standard_button(
            "Save text",
            role="neutral",
            parent=segment_panel,
        )
        self.regenerate_button = standard_button(
            "Regenerate selected",
            role="primary",
            parent=segment_panel,
        )
        segment_actions = QHBoxLayout()
        segment_actions.setSpacing(CONTROL_SPACING)
        segment_actions.addWidget(self.play_segment_button)
        segment_actions.addWidget(self.save_segment_button)
        segment_actions.addWidget(self.regenerate_button)
        self.segment_actions_layout = segment_actions
        self.segment_action_buttons = (
            self.play_segment_button,
            self.save_segment_button,
            self.regenerate_button,
        )
        for button in self.segment_action_buttons:
            button.hide()
        segment_header.addLayout(segment_actions)
        segment_layout.addLayout(segment_header)

        self.segment_stack = QStackedWidget()
        self.segment_empty_state = EmptyStateWidget(
            "No segments to review",
            "Retained segments will appear here after generation.",
            "Go to scripts",
            icon=lucide_icon("list", color=SUBTEXT_0, size=24),
        )
        self.segment_empty_state.action_key = "scripts"
        segment_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.segment_table = QTableWidget(0, 6)
        self.segment_table.setHorizontalHeaderLabels((
            "Use",
            "Script",
            "Segment",
            "State",
            "Words",
            "Time",
        ))
        self.segment_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.segment_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.segment_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.segment_table.verticalHeader().setVisible(False)
        self.segment_table.horizontalHeader().setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )
        self.segment_table.horizontalHeader().setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.Stretch,
        )
        segment_splitter.addWidget(self.segment_table)
        self.segment_editor = QPlainTextEdit()
        self.segment_editor.setPlaceholderText(
            "Select a retained segment to review or edit its text."
        )
        self.segment_editor.setAccessibleName("Selected segment text")
        segment_splitter.addWidget(self.segment_editor)
        segment_splitter.setSizes((700, 430))
        self.segment_stack.addWidget(self.segment_empty_state)
        self.segment_stack.addWidget(segment_splitter)
        self.segment_stack.setCurrentWidget(self.segment_empty_state)
        segment_layout.addWidget(self.segment_stack, 1)
        splitter.addWidget(segment_panel)
        splitter.setSizes((330, 400))
        outer.addWidget(splitter, 1)

        self.output_splitter = splitter
        self.segment_splitter = segment_splitter
        self.widget = tab


__all__ = ("OutputTabSection",)
