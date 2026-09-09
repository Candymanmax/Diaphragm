"""Script selection summaries and generation validation."""

from PySide6.QtCore import Qt

from harness_ui.dialogs import AppDialog


class ScriptSelectionCommands:
    """Expose checked scripts and validate a runnable selection."""

    def checked_paths(self):
        return [
            path
            for index in range(self.view.script_list.count())
            if (item := self.view.script_list.item(index)).checkState()
            == Qt.CheckState.Checked
            and (path := self.path_for_item(item)) is not None
        ]

    def update_summary(self, *args):
        del args
        script_list = self.view.script_list
        total = script_list.count()
        selected = sum(
            script_list.item(index).checkState() == Qt.CheckState.Checked
            for index in range(total)
        )
        has_current = script_list.currentItem() is not None
        self.view.script_summary.setText(
            f"{selected} of {total} script{'s' if total != 1 else ''} "
            "will be processed"
        )
        self.view.editor_stack.setCurrentWidget(
            self.view.editor_content
            if has_current
            else self.view.editor_empty_state
        )
        self.view.script_editor.setEnabled(has_current)
        self.view.script_save_action.setEnabled(has_current)
        self.view.save_as_button.setEnabled(has_current)
        self.view.delete_script_button.setEnabled(has_current)
        self._publish_snapshot()

    def checked_paths_for_run(self):
        if not self.save():
            return None
        unsaved_checked = [
            self.view.script_list.item(index)
            for index in range(self.view.script_list.count())
            if self.view.script_list.item(index).checkState()
            == Qt.CheckState.Checked
            and self.path_for_item(self.view.script_list.item(index)) is None
        ]
        if unsaved_checked:
            AppDialog.warning(
                self.parent_window,
                "Unsaved scripts",
                "Save each new script with Save or Save as… before running.",
            )
            return None

        scripts = self.checked_paths()
        if not scripts:
            AppDialog.warning(
                self.parent_window,
                "No scripts selected",
                "Check at least one script in the Scripts tab.",
            )
            return None

        unavailable = [path for path in scripts if not path.is_file()]
        if unavailable:
            AppDialog.warning(
                self.parent_window,
                "Script file unavailable",
                "These checked scripts were moved or deleted:\n\n"
                + "\n".join(path.name for path in unavailable)
                + "\n\nRemove them from the list or use Save as… before running.",
            )
            return None
        return scripts

    def exit_requires_confirmation(self):
        has_unsaved_script = any(
            self.path_for_item(self.view.script_list.item(index)) is None
            for index in range(self.view.script_list.count())
        )
        save_failed = self.current_path is not None and self.dirty and not self.save()
        return bool(save_failed or has_unsaved_script)
