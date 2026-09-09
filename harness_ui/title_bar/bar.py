from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QToolButton

from harness_ui.icons import lucide_icon
from harness_ui.theme import SUBTEXT_1

from .menu_bar import TitleBarMenuBar


class FramelessTitleBar(QFrame):
    """The visible, application-owned title bar."""

    HEIGHT = 34

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("appTitleBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(self.HEIGHT)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 0, 0)
        layout.setSpacing(0)

        self.menu_bar = TitleBarMenuBar(self)
        self.menu_bar.setObjectName("appMenuBar")
        self.menu_bar.setNativeMenuBar(False)
        self.menu_bar.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.menu_bar.setFixedHeight(self.HEIGHT)
        layout.addWidget(self.menu_bar, 1)

        self.minimize_button = self._caption_button(
            "titleBarMinimizeButton", "minus", "Minimize"
        )
        self.maximize_button = self._caption_button(
            "titleBarMaximizeButton", "square", "Maximize"
        )
        self.close_button = self._caption_button(
            "titleBarCloseButton", "x", "Close"
        )
        layout.addWidget(self.minimize_button)
        layout.addWidget(self.maximize_button)
        layout.addWidget(self.close_button)

    def _caption_button(self, object_name, icon_name, tooltip):
        button = QToolButton(self)
        button.setObjectName(object_name)
        button.setIcon(lucide_icon(icon_name, color=SUBTEXT_1, size=16))
        button.setIconSize(button.icon().actualSize(button.sizeHint()))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setAutoRaise(True)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setFixedSize(38, self.HEIGHT)
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        return button
