"""Qt-only frameless movement, resizing, and caption controls."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer, Qt
from PySide6.QtWidgets import QApplication, QWidget

from harness_ui.icons import lucide_icon
from harness_ui.theme import SUBTEXT_1

from .bar import FramelessTitleBar


class FramelessWindowController(QObject):
    """Add Qt-only movement, resizing, and caption controls to a window."""

    RESIZE_MARGIN = 6

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.title_bar = None
        self._resizing = False
        self._last_resize_edges = Qt.Edge(0)
        self._application = QApplication.instance()
        self.window.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)

        if self._application is not None:
            self._application.installEventFilter(self)

    def create_menu_bar(self):
        if self.title_bar is None:
            self.title_bar = FramelessTitleBar(self.window)
            self.window.setMenuWidget(self.title_bar)
            self.title_bar.minimize_button.clicked.connect(
                self.window.showMinimized
            )
            self.title_bar.maximize_button.clicked.connect(
                self.toggle_maximized
            )
            self.title_bar.close_button.clicked.connect(self.window.close)
            self.update_maximize_button()

        return self.title_bar.menu_bar

    def toggle_maximized(self):
        if self.window.isMaximized():
            self.window.showNormal()
        else:
            self.window.showMaximized()
        QTimer.singleShot(0, self.update_maximize_button)

    def update_maximize_button(self):
        if self.title_bar is None:
            return

        maximized = self.window.isMaximized()
        icon_name = "copy" if maximized else "square"
        tooltip = "Restore" if maximized else "Maximize"
        button = self.title_bar.maximize_button
        button.setIcon(lucide_icon(icon_name, color=SUBTEXT_1, size=16))
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)

    def eventFilter(self, watched, event):
        event_type = event.type()

        if watched is self.window:
            if event_type == QEvent.Type.Close:
                self._resizing = False
                self._clear_resize_cursor()
                if self._application is not None:
                    self._application.removeEventFilter(self)
                return super().eventFilter(watched, event)
            if event_type == QEvent.Type.WindowStateChange:
                if self.window.isMaximized() or self.window.isFullScreen():
                    self._resizing = False
                    self._clear_resize_cursor()
                QTimer.singleShot(0, self.update_maximize_button)
                return super().eventFilter(watched, event)
            if event_type in (
                QEvent.Type.Hide,
                QEvent.Type.WindowDeactivate,
            ):
                self._resizing = False
                self._clear_resize_cursor()
                return super().eventFilter(watched, event)

        if watched is self._application and event_type in (
            QEvent.Type.ApplicationDeactivate,
        ):
            self._resizing = False
            self._clear_resize_cursor()
            return super().eventFilter(watched, event)

        if event_type not in (
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonRelease,
            QEvent.Type.MouseMove,
            QEvent.Type.Leave,
        ):
            return super().eventFilter(watched, event)

        if not isinstance(watched, QWidget):
            return super().eventFilter(watched, event)

        if watched.window() is not self.window:
            return super().eventFilter(watched, event)

        if event_type == QEvent.Type.MouseButtonPress:
            return self._handle_mouse_press(event)

        if event_type == QEvent.Type.MouseButtonRelease:
            self._resizing = False
            self._clear_resize_cursor()
            return super().eventFilter(watched, event)

        if event_type == QEvent.Type.MouseMove:
            if not self._resizing:
                self._update_resize_cursor(event)
            return super().eventFilter(watched, event)

        if event_type == QEvent.Type.Leave and not self._resizing:
            self._clear_resize_cursor()

        return super().eventFilter(watched, event)

    def _handle_mouse_press(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return False

        edges = self._edges_at_global(event.globalPosition().toPoint())
        if not edges:
            return False

        window_handle = self.window.windowHandle()
        if window_handle is None:
            return False

        if window_handle.startSystemResize(edges):
            self._resizing = True
            return True

        return False

    def _update_resize_cursor(self, event):
        if self.window.isMaximized() or self.window.isFullScreen():
            self._clear_resize_cursor()
            return

        edges = self._edges_at_global(event.globalPosition().toPoint())
        if edges == self._last_resize_edges:
            return

        self._last_resize_edges = edges
        if not edges:
            self._clear_resize_cursor()
            return

        self.window.setCursor(self._cursor_for_edges(edges))

    def _clear_resize_cursor(self):
        # Always clear the widget cursor, even if the edge state was already
        # reset.  This prevents a resize cursor from becoming sticky when Qt
        # drops a leave/deactivation event while the pointer crosses a child
        # widget or the window changes state.
        self.window.unsetCursor()
        self._last_resize_edges = Qt.Edge(0)

    def _edges_at_global(self, global_point):
        if self.window.isMaximized() or self.window.isFullScreen():
            return Qt.Edge(0)

        point = self.window.mapFromGlobal(global_point)
        margin = self.RESIZE_MARGIN
        width = self.window.width()
        height = self.window.height()
        if point.x() < 0 or point.y() < 0:
            return Qt.Edge(0)
        if point.x() >= width or point.y() >= height:
            return Qt.Edge(0)

        edges = Qt.Edge(0)
        if point.x() <= margin:
            edges |= Qt.Edge.LeftEdge
        elif point.x() >= width - margin:
            edges |= Qt.Edge.RightEdge

        if point.y() <= margin:
            edges |= Qt.Edge.TopEdge
        elif point.y() >= height - margin:
            edges |= Qt.Edge.BottomEdge

        return edges

    @staticmethod
    def _cursor_for_edges(edges):
        left = bool(edges & Qt.Edge.LeftEdge)
        right = bool(edges & Qt.Edge.RightEdge)
        top = bool(edges & Qt.Edge.TopEdge)
        bottom = bool(edges & Qt.Edge.BottomEdge)

        if (left and top) or (right and bottom):
            return Qt.CursorShape.SizeFDiagCursor
        if (right and top) or (left and bottom):
            return Qt.CursorShape.SizeBDiagCursor
        if left or right:
            return Qt.CursorShape.SizeHorCursor
        return Qt.CursorShape.SizeVerCursor
