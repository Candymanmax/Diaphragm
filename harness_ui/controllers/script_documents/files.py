"""File-system commands for script documents."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QListWidgetItem

from harness_ui.controllers.script_documents.state import SCRIPT_TEXT_ROLE
from harness_ui.dialogs import AppDialog, RecycleBinDialog


class ScriptFileCommands:
    """Load, save, and safely delete script files."""

    def choose_files(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self.parent_window,
            "Add text scripts",
            str(self.project_root / "input"),
            "Text scripts (*.txt)",
        )
        if paths:
            self.add_paths(paths)

    def add_paths(self, paths):
        script_list = self.view.script_list
        known = {
            path
            for index in range(script_list.count())
            if (path := self.path_for_item(script_list.item(index))) is not None
        }
        first_new = None

        for value in paths:
            path = Path(value).expanduser().resolve()
            if not path.is_file() or path.suffix.lower() != ".txt":
                continue
            if path in known:
                continue
            try:
                script_text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                script_text = ""

            item = QListWidgetItem()
            # The row already shows the filename and the editor shows the
            # project-relative path; avoid exposing a full-path hover popup.
            item.setToolTip("")
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsEnabled
            )
            item.setCheckState(Qt.CheckState.Checked)
            self.set_item_text(item, path, script_text)
            script_list.addItem(item)
            known.add(path)
            first_new = first_new or item

        if script_list.currentItem() is None and script_list.count():
            script_list.setCurrentItem(first_new or script_list.item(0))
        self.update_summary()

    def add_dropped_paths(self, paths):
        """Add dropped scripts as unsaved, in-memory drafts."""

        script_list = self.view.script_list
        first_new = None
        added_count = 0
        failures = []

        for value in paths:
            source = Path(value).expanduser().resolve()
            if not source.is_file() or source.suffix.lower() != ".txt":
                continue

            try:
                script_text = source.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as error:
                failures.append(f"{source.name}: {error}")
                continue

            item = self._new_memory_item(script_text)
            script_list.addItem(item)
            first_new = first_new or item
            added_count += 1

        if script_list.currentItem() is None and first_new is not None:
            script_list.setCurrentItem(first_new)
        self.update_summary()

        if added_count:
            label = "unsaved script" if added_count == 1 else "unsaved scripts"
            self._status_message(f"Added {added_count} {label}", 5000)

        if failures:
            self._set(
                "workspace_error_message",
                "Could not read dropped scripts:\n\n"
                + "\n".join(failures),
            )

    def delete_current(self):
        script_list = self.view.script_list
        row = script_list.currentRow()
        if row < 0:
            return

        item = script_list.item(row)
        path = self.path_for_item(item)
        if path is None:
            self.remove_row(row)
            self._status_message("Discarded unsaved script", 5000)
            return

        unsaved = (
            self.current_path is not None
            and path.resolve() == self.current_path.resolve()
            and self.dirty
        )
        detail = (
            "\n\nUnsaved editor changes will also be discarded."
            if unsaved
            else ""
        )
        if not RecycleBinDialog.confirm(self.parent_window, path.name, detail):
            return

        self.autosave_timer.stop()
        existed = path.exists()
        if existed:
            try:
                moved = self._move_to_trash(path)
            except OSError as error:
                AppDialog.critical(
                    self.parent_window,
                    "Could not delete script",
                    str(error),
                )
                return
            if not moved:
                AppDialog.critical(
                    self.parent_window,
                    "Could not delete script",
                    "Windows could not move the file to the Recycle Bin. "
                    "The file was left unchanged.",
                )
                return

        self.remove_row(row)
        self._status_message(
            (
                f"Moved {path.name} to the Recycle Bin"
                if existed
                else f"Removed missing file {path.name} from the list"
            ),
            5000,
        )

    def delete_row(self, row):
        """Delete the row that owns a list-level delete action."""

        script_list = self.view.script_list
        row = int(row)
        if row < 0 or row >= script_list.count():
            return

        if script_list.currentRow() != row:
            script_list.setCurrentRow(row)
            # A failed save can reject the selection change. Never delete a
            # different row if that happens.
            if script_list.currentRow() != row:
                return

        self.delete_current()

    def save(self):
        self.autosave_timer.stop()
        if self.view.script_list.currentItem() is None:
            return True
        if self.current_path is None:
            return bool(self.save_as())
        if not self.dirty:
            return True
        if not self.current_path.is_file():
            self.view.script_save_state.setText("File missing — use Save as…")
            self._set(
                "workspace_error_message",
                f"The script was moved or deleted: {self.current_path}. "
                "Use Save as… to keep the editor contents.",
            )
            return False

        try:
            self._atomic_write_text(
                self.current_path,
                self.view.script_editor.toPlainText(),
            )
        except OSError as error:
            self.view.script_save_state.setText("Save failed")
            self._set("workspace_error_message", str(error))
            return False

        self.dirty = False
        self.view.script_save_state.setText("Saved")
        self._publish_snapshot()
        return True

    def save_as(self):
        current_item = self.view.script_list.currentItem()
        if current_item is None:
            return False

        suggested = self.current_path or (
            self.project_root / "input" / "new-script.txt"
        )
        path, _ = QFileDialog.getSaveFileName(
            self.parent_window,
            "Save script as",
            str(suggested),
            "Text scripts (*.txt)",
        )
        if not path:
            return False
        path = Path(path).expanduser().resolve()
        if path.suffix.lower() != ".txt":
            path = path.with_suffix(".txt")

        try:
            self._atomic_write_text(path, self.view.script_editor.toPlainText())
        except OSError as error:
            AppDialog.critical(
                self.parent_window,
                "Could not save script",
                str(error),
            )
            return False

        self.autosave_timer.stop()
        self.dirty = False
        if self.current_path is None:
            duplicate = self.find_item(path, exclude=current_item)
            if duplicate is not None:
                self.view.script_list.takeItem(self.view.script_list.row(duplicate))
            current_item.setData(Qt.ItemDataRole.UserRole, str(path))
            current_item.setData(SCRIPT_TEXT_ROLE, None)
            current_item.setToolTip("")
            self.current_path = path
            self.set_item_text(
                current_item,
                path,
                self.view.script_editor.toPlainText(),
            )
        else:
            self.current_path = path
            self.add_paths((path,))
            for index in range(self.view.script_list.count()):
                item = self.view.script_list.item(index)
                if self.path_for_item(item) == path:
                    self.view.script_list.setCurrentItem(item)
                    break

        self.view.editor_path.setText(self.display_path(path))
        self.view.editor_path.setToolTip("")
        self.view.script_save_state.setText("Saved")
        self.update_metrics()
        self.update_summary()
        return True
