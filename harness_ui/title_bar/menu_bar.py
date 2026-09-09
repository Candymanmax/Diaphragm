from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMenu,
    QSizePolicy,
    QToolButton,
    QWidget,
    QWidgetAction,
)

from harness_ui.theme import MICRO_SPACING


class TitleBarMenuBar(QWidget):
    """Safe Qt menu strip with explicit hoverable menu buttons."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._menu_buttons = {}
        self._active_menu_button = None
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(2, 0, 6, 0)
        self._layout.setSpacing(MICRO_SPACING)
        self._layout.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )

    def setNativeMenuBar(self, enabled):
        del enabled

    def addAction(self, action):
        super().addAction(action)
        if isinstance(action, QWidgetAction):
            widget = action.defaultWidget()
            if widget is not None:
                self._layout.addWidget(widget)
                widget.show()
        return action

    def addMenu(self, title):
        menu = QMenu(title, self)
        button = QToolButton(self)
        button.setObjectName("titleBarMenuButton")
        button.setText(title)
        button.setMenu(menu)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        button.setAutoRaise(True)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setFixedHeight(28)
        button.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        button.setCheckable(True)
        button.setAccessibleName(title)
        button.setToolTip(title)
        menu.aboutToShow.connect(
            lambda menu_button=button: self._activate_menu_button(menu_button)
        )
        menu.aboutToHide.connect(self._schedule_active_menu_sync)
        button.clicked.connect(
            lambda checked=False, menu_button=button: (
                self._activate_menu_button(menu_button)
            )
        )
        widget_action = QWidgetAction(self)
        widget_action.setDefaultWidget(button)
        self.addAction(widget_action)
        self._menu_buttons[menu] = button
        return menu

    def _activate_menu_button(self, button):
        for menu_button in self._menu_buttons.values():
            menu_button.setChecked(menu_button is button)
        self._active_menu_button = button

    def _schedule_active_menu_sync(self):
        QTimer.singleShot(0, self._sync_active_menu_button)

    def _sync_active_menu_button(self):
        visible_menu_button = None
        for menu, button in self._menu_buttons.items():
            if menu.isVisible():
                visible_menu_button = button
                break

        if visible_menu_button is not None:
            self._activate_menu_button(visible_menu_button)
            return

        for button in self._menu_buttons.values():
            button.setChecked(False)
        self._active_menu_button = None

    @staticmethod
    def _window_from_widget(widget):
        return widget.window() if widget is not None else None

    def _is_blank_point(self, point):
        child = self.childAt(point)
        return child is None or child is self

    def _start_system_move(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return False

        if not self._is_blank_point(event.position().toPoint()):
            return False

        window = self._window_from_widget(self)
        window_handle = window.windowHandle() if window is not None else None
        if window_handle is None:
            return False

        if window_handle.startSystemMove():
            event.accept()
            return True

        return False

    def mousePressEvent(self, event):
        if self._start_system_move(event):
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._is_blank_point(event.position().toPoint())
        ):
            window = self._window_from_widget(self)
            if window is not None:
                if window.isMaximized():
                    window.showNormal()
                else:
                    window.showMaximized()
                event.accept()
                return

        super().mouseDoubleClickEvent(event)
