"""In-memory draft and editor-session behavior."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem

from harness_ui.controllers.script_documents.state import SCRIPT_TEXT_ROLE
from harness_ui.dialogs import AppDialog


class ScriptEditorCommands:
    """Coordinate current-item selection, draft text, and editor metrics."""

    def _new_memory_item(self, text=""):
        """Create the same unsaved list item used by New script."""

        item = QListWidgetItem()
        item.setToolTip(
            "This script has not been saved yet. Use Save or Save as… "
            "to choose a filename."
        )
        item.setData(Qt.ItemDataRole.UserRole, None)
        item.setData(SCRIPT_TEXT_ROLE, str(text))
        item.setFlags(
            item.flags()
            | Qt.ItemFlag.ItemIsUserCheckable
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsEnabled
        )
        item.setCheckState(Qt.CheckState.Checked)
        self.set_item_text(item, "Untitled script", text)
        return item

    def new_document(self):
        if self.dirty and not self.save():
            return False

        item = self._new_memory_item()
        self.view.script_list.addItem(item)
        self.view.script_list.setCurrentItem(item)
        self.update_summary()
        self.view.script_editor.setFocus()
        return True

    def remove_current(self):
        row = self.view.script_list.currentRow()
        if row < 0:
            return
        item = self.view.script_list.item(row)
        if self.path_for_item(item) is None:
            self.remove_row(row)
            self._status_message("Discarded unsaved script", 5000)
            return
        if not self.save():
            return
        self.remove_row(row)

    def remove_row(self, row):
        self.autosave_timer.stop()
        script_list = self.view.script_list
        script_list.blockSignals(True)
        try:
            script_list.takeItem(row)
            if script_list.count():
                script_list.setCurrentRow(min(row, script_list.count() - 1))
        finally:
            script_list.blockSignals(False)

        next_item = script_list.currentItem()
        self.clear_editor()
        if next_item is not None:
            self.select_document(next_item, None)
        self.update_summary()

    def clear_editor(self):
        self.loading = True
        try:
            self.current_path = None
            self.view.script_editor.clear()
        finally:
            self.loading = False
        self.dirty = False
        self.view.editor_path.setText("Select a script to edit")
        self.view.editor_path.setToolTip("")
        self.view.script_save_state.clear()
        self.update_metrics()

    def select_document(self, current, previous):
        if current is None:
            return
        self.autosave_timer.stop()
        if previous is not None and self.current_path is None:
            previous.setData(SCRIPT_TEXT_ROLE, self.view.script_editor.toPlainText())
        if self.dirty and self.current_path is not None and not self.save():
            if previous is not None:
                self.view.script_list.blockSignals(True)
                self.view.script_list.setCurrentItem(previous)
                self.view.script_list.blockSignals(False)
            return

        path = self.path_for_item(current)
        if path is None:
            text = current.data(SCRIPT_TEXT_ROLE) or ""
        else:
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as error:
                AppDialog.critical(
                    self.parent_window,
                    "Could not open script",
                    str(error),
                )
                if previous is not None:
                    self.view.script_list.blockSignals(True)
                    self.view.script_list.setCurrentItem(previous)
                    self.view.script_list.blockSignals(False)
                return

        self.loading = True
        try:
            self.current_path = path
            self.view.script_editor.setPlainText(text)
        finally:
            self.loading = False
        self.dirty = False

        if path is None:
            self.view.editor_path.setText("Untitled script")
            self.view.editor_path.setToolTip(
                "This script has not been saved yet. Use Save or Save as… "
                "to choose a filename."
            )
            self.view.script_save_state.setText("Not saved")
        else:
            self.view.editor_path.setText(self.display_path(path))
            # Keep the editor header concise; the full path is not useful as
            # a hover popup when the displayed project-relative path is clear.
            self.view.editor_path.setToolTip("")
            self.view.script_save_state.setText("Saved")
        self.update_metrics()
        self.update_summary()

    def document_changed(self):
        self.update_metrics()
        current = self.view.script_list.currentItem()
        if self.loading or current is None:
            return
        self.dirty = True
        if self.current_path is None:
            current.setData(SCRIPT_TEXT_ROLE, self.view.script_editor.toPlainText())
            self.view.script_save_state.setText("Not saved")
            self._publish_snapshot()
            return
        self.view.script_save_state.setText("Saving…")
        self.autosave_timer.start()
        self._publish_snapshot()

    def set_line_numbers(self, visible, *, persist=True):
        visible = bool(visible)
        self.state.set("line_numbers_visible", visible)
        self.view.script_editor.set_line_numbers_visible(visible)
        self.view.script_line_numbers_action.blockSignals(True)
        self.view.script_line_numbers_action.setChecked(visible)
        self.view.script_line_numbers_action.blockSignals(False)
        if persist:
            self.settings_repository.set_value("editor/show_line_numbers", visible)

    def update_metrics(self):
        text = self.view.script_editor.toPlainText()
        self.view.editor_metrics.setText(
            f"{len(text.split()):,} words · {len(text):,} characters"
        )
        current = self.view.script_list.currentItem()
        if current is not None:
            path = self.path_for_item(current)
            self.set_item_text(current, path or "Untitled script", text)
