"""Context-menu composition for script items."""

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMenu


class ScriptMenuCommands:
    """Build and show context-sensitive script actions."""

    @staticmethod
    def _named_menu_action(menu, text, object_name):
        action = menu.addAction(text)
        action.setObjectName(object_name)
        return action

    def build_context_menu(self, item):
        menu = QMenu(self.view.script_list)
        menu.setObjectName("scriptContextMenu")
        path = self.path_for_item(item)

        include_action = self._named_menu_action(
            menu, "Include in job", "scriptContextInclude"
        )
        include_action.setCheckable(True)
        include_action.setChecked(item.checkState() == Qt.CheckState.Checked)
        include_action.toggled.connect(
            lambda checked, target=item: target.setCheckState(
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            )
        )

        save_action = self._named_menu_action(menu, "Save", "scriptContextSave")
        save_action.setEnabled(path is None or path.exists())
        save_action.triggered.connect(self.save)
        save_as_action = self._named_menu_action(
            menu, "Save as…", "scriptContextSaveAs"
        )
        save_as_action.triggered.connect(self.save_as)
        if path is not None:
            reveal_action = self._named_menu_action(
                menu,
                "Open containing folder",
                "scriptContextReveal",
            )
            reveal_action.setEnabled(path.parent.exists())
            reveal_action.triggered.connect(
                lambda checked=False, folder=path.parent: QDesktopServices.openUrl(
                    QUrl.fromLocalFile(str(folder))
                )
            )

        menu.addSeparator()
        remove_action = self._named_menu_action(
            menu,
            "Remove from list",
            "scriptContextRemove",
        )
        remove_action.setToolTip(
            "Discard this unsaved script without saving"
            if path is None
            else "Keep the text file and remove only this list entry"
        )
        remove_action.triggered.connect(self.remove_current)
        delete_action = self._named_menu_action(
            menu,
            "Delete file…" if path is not None else "Discard script…",
            "scriptContextDelete",
        )
        delete_action.setToolTip(
            "Move the text file to the Recycle Bin"
            if path is not None
            else "Discard this unsaved script"
        )
        delete_action.triggered.connect(self.delete_current)
        return menu

    def show_context_menu(self, position):
        item = self.view.script_list.itemAt(position)
        if item is None:
            return
        self.view.script_list.setCurrentItem(item)
        menu = self.build_context_menu(item)
        menu.exec(self.view.script_list.viewport().mapToGlobal(position))
