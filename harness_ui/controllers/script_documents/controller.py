"""Composed controller for script-document lifecycle behavior."""

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, Qt, QTimer, Signal

from harness_ui.controllers.script_documents.editor import ScriptEditorCommands
from harness_ui.controllers.script_documents.files import ScriptFileCommands
from harness_ui.controllers.script_documents.items import ScriptItemSupport
from harness_ui.controllers.script_documents.menus import ScriptMenuCommands
from harness_ui.controllers.script_documents.selection import ScriptSelectionCommands
from harness_ui.controllers.script_documents.state import ScriptDocumentSnapshot
from harness_ui.state import UiStateStore


class ScriptDocumentController(
    ScriptFileCommands,
    ScriptEditorCommands,
    ScriptMenuCommands,
    ScriptSelectionCommands,
    ScriptItemSupport,
    QObject,
):
    """Coordinate script files, in-memory drafts, and editor state."""

    snapshotChanged = Signal(object)

    def __init__(
        self,
        *,
        parent,
        view,
        state: UiStateStore,
        project_root,
        settings_repository,
        atomic_write_text: Callable[[Path, str], None],
        move_to_trash: Callable[[Path], bool],
        status_message: Callable[[str, int], None],
    ):
        super().__init__(parent)
        self.parent_window = parent
        self.view = view
        self.state = state
        self.project_root = Path(project_root).resolve()
        self.settings_repository = settings_repository
        self._atomic_write_text = atomic_write_text
        self._move_to_trash = move_to_trash
        self._status_message = status_message

        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.setInterval(800)
        self.autosave_timer.timeout.connect(self.save)

    @property
    def current_path(self):
        return self.state.get("current_script_path")

    @current_path.setter
    def current_path(self, value):
        self.state.set("current_script_path", value)

    @property
    def loading(self):
        return bool(self.state.get("script_loading"))

    @loading.setter
    def loading(self, value):
        self.state.set("script_loading", bool(value))

    @property
    def dirty(self):
        return bool(self.state.get("script_dirty"))

    @dirty.setter
    def dirty(self, value):
        self.state.set("script_dirty", bool(value))

    def snapshot(self):
        script_list = self.view.script_list
        text = self.view.script_editor.toPlainText()
        paths = [
            self.path_for_item(script_list.item(index))
            for index in range(script_list.count())
        ]
        return ScriptDocumentSnapshot(
            current_path=self.current_path,
            dirty=self.dirty,
            loading=self.loading,
            total_documents=script_list.count(),
            selected_documents=sum(
                script_list.item(index).checkState() == Qt.CheckState.Checked
                for index in range(script_list.count())
            ),
            has_current_document=script_list.currentItem() is not None,
            has_unsaved_documents=any(path is None for path in paths),
            word_count=len(text.split()),
            character_count=len(text),
        )

    def _publish_snapshot(self):
        self.snapshotChanged.emit(self.snapshot())

    def _set(self, field, value):
        """Publish a script-owned or shared state transition."""

        self.state.set(field, value)
