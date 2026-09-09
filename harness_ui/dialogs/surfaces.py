"""Shared painted surfaces for Diaphragm's frameless dialogs."""

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QLineEdit

from harness_ui.theme import (
    BASE,
    CONTROL_SPACING,
    MANTLE,
    SURFACE_1,
    SURFACE_2,
    active_accent_color,
)


class RoundedDialogPanel(QFrame):
    """Anti-aliased surface for translucent frameless dialogs."""

    def paintEvent(self, event):
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor(SURFACE_1), 1.0))
        painter.setBrush(QColor(BASE))
        painter.drawRoundedRect(
            QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5),
            12.0,
            12.0,
        )
        painter.end()


class RoundedJobNameInput(QLineEdit):
    """Line edit with a continuous high-DPI rounded outline."""

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        border = (
            active_accent_color()
            if self.hasFocus()
            else SURFACE_2
            if self.underMouse()
            else SURFACE_1
        )
        painter.setPen(QPen(QColor(border), 1.0))
        painter.setBrush(QColor(MANTLE))
        painter.drawRoundedRect(
            QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5),
            7.0,
            7.0,
        )
        painter.end()
        super().paintEvent(event)

    def enterEvent(self, event):
        super().enterEvent(event)
        self.update()

    def leaveEvent(self, event):
        super().leaveEvent(event)
        self.update()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.update()
