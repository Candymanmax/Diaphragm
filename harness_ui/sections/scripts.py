"""Script selection and editing workspace."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPlainTextEdit,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from harness_ui.icons import lucide_icon
from harness_ui.sections.base import CONTROL_SPACING, StatefulSection
from harness_ui.state import UiStateStore
from harness_ui.theme import (
    INLINE_SPACING,
    RED,
    SECTION_SPACING,
    SUBTEXT_0,
    TEXT,
    icon_button,
    standard_button,
)
from harness_ui.widgets import (
    ScriptDropEmptyState,
    ScriptEditor,
    ScriptListWidget,
)


class ScriptsTabSection(StatefulSection):
    def __init__(self, state: UiStateStore, settings_store, parent=None):
        super().__init__(state)
        tab = QWidget(parent)
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 10, 0, 0)
        layout.setSpacing(SECTION_SPACING)

        self.script_summary = QLabel("No scripts selected")
        self.script_summary.setProperty("muted", True)
        layout.addWidget(self.script_summary)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        self.script_list = ScriptListWidget()
        self.script_list.setObjectName("scriptList")
        self.script_list.setMinimumWidth(220)
        self.script_list.setMaximumWidth(260)
        self.script_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.script_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        splitter.addWidget(self.script_list)

        editor_panel = QWidget()
        editor_layout = QVBoxLayout(editor_panel)
        editor_layout.setContentsMargins(10, 0, 0, 0)
        editor_layout.setSpacing(INLINE_SPACING)
        editor_header = QHBoxLayout()
        editor_header.setSpacing(CONTROL_SPACING)
        self.editor_path = QLabel("Select a script to edit")
        self.editor_path.setObjectName("editorPath")
        self.editor_path.setProperty("muted", True)
        self.editor_path.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        self.editor_path.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.script_save_state = QLabel()
        self.script_save_state.setProperty("muted", True)
        self.new_script_button = standard_button(
            "New script",
            role="neutral",
            parent=editor_panel,
        )
        self.save_as_button = standard_button(
            "Save as…",
            role="neutral",
            parent=editor_panel,
        )
        self.delete_script_button = icon_button(
            lucide_icon("trash-2", color=RED, size=16),
            role="danger",
            parent=editor_panel,
            object_name="scriptDeleteButton",
            icon_size=16,
            size=36,
            accessible_name="Delete script",
            auto_raise=False,
        )
        self.script_menu_button = icon_button(
            lucide_icon("ellipsis", color=TEXT, size=18),
            role="neutral",
            parent=editor_panel,
            object_name="scriptMenuButton",
            icon_size=18,
            size=36,
            accessible_name="More script actions",
            tool_tip="More script actions",
            auto_raise=False,
        )
        self.script_menu_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup
        )
        self.script_menu = QMenu(self.script_menu_button)
        self.script_menu.setObjectName("scriptMenu")
        self.script_save_action = self.script_menu.addAction("Save")
        self.script_add_action = self.script_menu.addAction("Add scripts…")
        self.script_menu.addSeparator()
        self.script_line_numbers_action = self.script_menu.addAction(
            "Show line numbers"
        )
        self.script_line_numbers_action.setCheckable(True)
        show_line_numbers = settings_store.value(
            "editor/show_line_numbers",
            True,
            type=bool,
        )
        self.script_line_numbers_action.setChecked(show_line_numbers)
        self.script_menu_button.setMenu(self.script_menu)
        editor_header.addWidget(self.editor_path, 1)
        editor_header.addWidget(self.script_save_state)
        editor_actions = QHBoxLayout()
        editor_actions.setSpacing(CONTROL_SPACING)
        editor_actions.addWidget(self.new_script_button)
        editor_actions.addWidget(self.save_as_button)
        editor_actions.addWidget(self.delete_script_button)
        editor_actions.addWidget(self.script_menu_button)
        self.editor_actions_layout = editor_actions
        editor_header.addLayout(editor_actions)
        editor_layout.addLayout(editor_header)

        self.editor_stack = QStackedWidget()
        self.editor_stack.setObjectName("scriptEditorStack")
        self.editor_empty_state = ScriptDropEmptyState(
            "No script selected",
            "Drop a .txt file here, or choose an option below.",
            "New script",
            icon=lucide_icon("list", color=SUBTEXT_0, size=24),
            action_role="primary",
            secondary_action_text="Browse files…",
        )
        self.editor_empty_state.setAccessibleName("No script selected")

        editor_content = QWidget()
        editor_content_layout = QVBoxLayout(editor_content)
        editor_content_layout.setContentsMargins(0, 0, 0, 0)
        editor_content_layout.setSpacing(INLINE_SPACING)
        self.script_editor = ScriptEditor()
        self.script_editor.setObjectName("scriptEditor")
        self.script_editor.set_line_numbers_visible(show_line_numbers)
        self.script_editor.setPlaceholderText(
            "Write or paste the words you want to synthesize…"
        )
        self.script_editor.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.WidgetWidth
        )
        self.script_editor.setAccessibleName("TTS script editor")
        editor_content_layout.addWidget(self.script_editor, 1)
        self.editor_metrics = QLabel("0 words · 0 characters")
        self.editor_metrics.setProperty("muted", True)
        editor_content_layout.addWidget(self.editor_metrics)
        self.editor_stack.addWidget(self.editor_empty_state)
        self.editor_stack.addWidget(editor_content)
        self.editor_stack.setCurrentWidget(self.editor_empty_state)
        self.editor_content = editor_content
        editor_layout.addWidget(self.editor_stack, 1)
        splitter.addWidget(editor_panel)
        splitter.setSizes((240, 900))
        layout.addWidget(splitter, 1)

        self.script_splitter = splitter
        self.widget = tab


__all__ = ("ScriptsTabSection",)
