"""Script-list item representation and path helpers."""

from pathlib import Path

from PySide6.QtCore import Qt


class ScriptItemSupport:
    """Translate between list items, script paths, and display text."""

    @staticmethod
    def set_item_text(item, path, text):
        words = len(str(text).split())
        word_label = "word" if words == 1 else "words"
        item.setText(f"{Path(path).name}\n{words:,} {word_label}")

    @staticmethod
    def path_for_item(item):
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        if not value:
            return None
        return Path(value).expanduser().resolve()

    def find_item(self, path, exclude=None):
        target = Path(path).expanduser().resolve()
        script_list = self.view.script_list
        for index in range(script_list.count()):
            item = script_list.item(index)
            if item is exclude:
                continue
            if self.path_for_item(item) == target:
                return item
        return None

    def display_path(self, path):
        path = Path(path).resolve()
        try:
            return path.relative_to(self.project_root).as_posix()
        except ValueError:
            return path.name
