from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QTimer, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QListWidget

from harness_ui.icons import lucide_icon
from harness_ui.theme import OVERLAY_0, icon_button
from .empty_state import EmptyStateWidget
from .focus_list import KeyboardFocusListWidget


class _TextFileDropTarget:
    """Add consistent text-file drag-and-drop feedback to a widget."""

    def _has_text_files(self, event):
        return event.mimeData().hasUrls() and any(
            url.isLocalFile()
            and Path(url.toLocalFile()).suffix.lower() == ".txt"
            for url in event.mimeData().urls()
        )

    def _text_file_paths(self, event):
        return [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.isLocalFile()
            and Path(url.toLocalFile()).suffix.lower() == ".txt"
        ]

    def _set_drop_active(self, active):
        active = bool(active)
        if active == bool(self.property("dropActive")):
            return

        self.setProperty("dropActive", active)
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.update()

    def dragEnterEvent(self, event):
        if self._has_text_files(event):
            self._set_drop_active(True)
            event.acceptProposedAction()
            return

        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if self._has_text_files(event):
            self._set_drop_active(True)
            event.acceptProposedAction()
            return

        self._set_drop_active(False)
        super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        self._set_drop_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        try:
            paths = self._text_file_paths(event)
            if paths:
                self.filesDropped.emit(paths)
                event.acceptProposedAction()
                return

            super().dropEvent(event)
        finally:
            self._set_drop_active(False)


class ScriptDropEmptyState(_TextFileDropTarget, EmptyStateWidget):
    """Centered empty editor state that also acts as a script drop target."""

    filesDropped = Signal(list)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAcceptDrops(True)
        self.setProperty("dropActive", False)


class ScriptListWidget(_TextFileDropTarget, KeyboardFocusListWidget):
    """Script list with drag feedback but no persistent mouse outline."""

    filesDropped = Signal(list)
    deleteRequested = Signal(int)
    contentsCleared = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setProperty("dropActive", False)
        self._delete_row = -1
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)

        self.delete_button = icon_button(
            lucide_icon("trash-2", color=OVERLAY_0, size=16),
            role="ghost",
            parent=self.viewport(),
            object_name="scriptRowDeleteButton",
            icon_size=16,
            size=24,
            accessible_name="Delete script",
            auto_raise=True,
        )
        self.delete_button.hide()
        self.delete_button.clicked.connect(self._request_delete)
        self.delete_button.installEventFilter(self)
        self.viewport().installEventFilter(self)
        self.itemEntered.connect(self._show_delete_for_item)
        self.verticalScrollBar().valueChanged.connect(
            self._sync_delete_button_from_cursor
        )
        self.horizontalScrollBar().valueChanged.connect(
            self._sync_delete_button_from_cursor
        )

    def clear(self):
        """Clear all rows and notify the controller of the empty state."""

        super().clear()
        self.contentsCleared.emit()

    def _cursor_row(self):
        if self.delete_button.isVisible():
            button_position = self.delete_button.mapFromGlobal(QCursor.pos())
            if self.delete_button.rect().contains(button_position):
                return self._delete_row

        position = self.viewport().mapFromGlobal(QCursor.pos())
        item = self.itemAt(position)
        return self.row(item) if item is not None else -1

    def _show_delete_for_item(self, item):
        self._set_delete_row(self.row(item) if item is not None else -1)

    def _set_delete_row(self, row):
        row = int(row)
        if row < 0 or row >= self.count():
            self._delete_row = -1
            self.delete_button.hide()
            return

        item_rect = self.visualItemRect(self.item(row))
        if not item_rect.isValid() or not item_rect.intersects(
            self.viewport().rect()
        ):
            self._delete_row = -1
            self.delete_button.hide()
            return

        button_width = self.delete_button.width()
        x = item_rect.x() + item_rect.width() - button_width - 6
        x = max(item_rect.left() + 4, x)
        x = min(x, self.viewport().width() - button_width - 4)
        y = item_rect.y() + (item_rect.height() - self.delete_button.height()) // 2
        self._delete_row = row
        self.delete_button.move(x, max(0, y))
        self.delete_button.show()
        self.delete_button.raise_()

    def _sync_delete_button_from_cursor(self, *_args):
        self._set_delete_row(self._cursor_row())

    def _request_delete(self, checked=False):
        del checked
        row = self._delete_row
        if row < 0:
            return

        self.delete_button.hide()
        self._delete_row = -1
        self.deleteRequested.emit(row)
        QTimer.singleShot(0, self._sync_delete_button_from_cursor)

    def eventFilter(self, watched, event):
        if watched is self.viewport():
            if event.type() == QEvent.Type.MouseMove:
                self._sync_delete_button_from_cursor()
            elif event.type() == QEvent.Type.Leave:
                QTimer.singleShot(0, self._sync_delete_button_from_cursor)
            elif event.type() == QEvent.Type.Resize:
                QTimer.singleShot(0, self._sync_delete_button_from_cursor)
        elif watched is self.delete_button:
            if event.type() == QEvent.Type.Leave:
                QTimer.singleShot(0, self._sync_delete_button_from_cursor)
        return super().eventFilter(watched, event)


__all__ = ("ScriptDropEmptyState", "ScriptListWidget")
