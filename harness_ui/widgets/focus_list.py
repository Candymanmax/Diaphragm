"""List widgets with a focus ring reserved for keyboard navigation."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidget


_KEYBOARD_FOCUS_REASONS = frozenset(
    (
        Qt.FocusReason.TabFocusReason,
        Qt.FocusReason.BacktabFocusReason,
        Qt.FocusReason.ShortcutFocusReason,
    )
)


class KeyboardFocusListWidget(QListWidget):
    """Keep mouse selection separate from keyboard focus styling."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("keyboardFocus", False)

    def _set_keyboard_focus(self, active):
        active = bool(active)
        if active == bool(self.property("keyboardFocus")):
            return

        self.setProperty("keyboardFocus", active)
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.update()

    def clear_keyboard_focus(self):
        """Clear the visual keyboard-focus state after a mouse selection."""

        self._set_keyboard_focus(False)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._set_keyboard_focus(event.reason() in _KEYBOARD_FOCUS_REASONS)

    def focusOutEvent(self, event):
        self._set_keyboard_focus(False)
        super().focusOutEvent(event)

    def mousePressEvent(self, event):
        self._set_keyboard_focus(False)
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        self._set_keyboard_focus(True)
        super().keyPressEvent(event)


__all__ = ("KeyboardFocusListWidget",)
