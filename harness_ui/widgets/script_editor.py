from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFontDatabase,
    QPainter,
    QTextBlockFormat,
    QTextCursor,
    QTextFormat,
)
from PySide6.QtWidgets import QPlainTextEdit, QTextEdit, QWidget

from harness_ui.theme import CRUST, OVERLAY_0, SURFACE_0, active_accent_color


_KEYBOARD_FOCUS_REASONS = frozenset(
    (
        Qt.FocusReason.TabFocusReason,
        Qt.FocusReason.BacktabFocusReason,
        Qt.FocusReason.ShortcutFocusReason,
    )
)


class _LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_line_number_area(event)


class ScriptEditor(QPlainTextEdit):
    """Writing-focused plain-text editor with optional line numbers."""

    lineNumbersVisibilityChanged = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setProperty("keyboardFocus", False)
        self._line_numbers_visible = True
        self.line_number_area = _LineNumberArea(self)

        editor_font = QFontDatabase.systemFont(
            QFontDatabase.SystemFont.FixedFont
        )
        current_size = editor_font.pointSizeF()
        editor_font.setPointSizeF(max(11.0, current_size + 1.0))
        self.setFont(editor_font)
        self.document().setDefaultFont(editor_font)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)

        self.blockCountChanged.connect(self._update_line_number_area_width)
        self.updateRequest.connect(self._update_line_number_area)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self._update_line_number_area_width()
        self._apply_line_spacing()
        self._highlight_current_line()

    def _set_keyboard_focus(self, active):
        active = bool(active)
        if active == bool(self.property("keyboardFocus")):
            return

        self.setProperty("keyboardFocus", active)
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.update()

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

    def setPlainText(self, text):
        super().setPlainText(text)
        self._apply_line_spacing()
        self._highlight_current_line()

    def _apply_line_spacing(self):
        document = self.document()
        undo_enabled = document.isUndoRedoEnabled()
        document.setUndoRedoEnabled(False)

        try:
            cursor = QTextCursor(document)
            cursor.select(QTextCursor.SelectionType.Document)
            block_format = QTextBlockFormat()
            block_format.setLineHeight(
                125.0,
                QTextBlockFormat.LineHeightTypes.ProportionalHeight.value,
            )
            cursor.mergeBlockFormat(block_format)
        finally:
            document.setUndoRedoEnabled(undo_enabled)

    def line_numbers_visible(self):
        return self._line_numbers_visible

    def set_line_numbers_visible(self, visible):
        visible = bool(visible)

        if visible == self._line_numbers_visible:
            return

        self._line_numbers_visible = visible
        self.line_number_area.setVisible(visible)
        self._update_line_number_area_width()
        self.lineNumbersVisibilityChanged.emit(visible)

    def line_number_area_width(self):
        if not self._line_numbers_visible:
            return 0

        digits = max(2, len(str(max(1, self.blockCount()))))
        return 14 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_line_number_area_width(self, *args):
        del args
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def _update_line_number_area(self, rect, dy):
        if not self._line_numbers_visible:
            return

        if dy:
            self.line_number_area.scroll(0, dy)
        else:
            self.line_number_area.update(
                0,
                rect.y(),
                self.line_number_area.width(),
                rect.height(),
            )

        if rect.contains(self.viewport().rect()):
            self._update_line_number_area_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        contents = self.contentsRect()
        self.line_number_area.setGeometry(QRect(
            contents.left(),
            contents.top(),
            self.line_number_area_width(),
            contents.height(),
        ))

    def paint_line_number_area(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor(CRUST))
        painter.setPen(QColor(SURFACE_0))
        painter.drawLine(
            self.line_number_area.width() - 1,
            event.rect().top(),
            self.line_number_area.width() - 1,
            event.rect().bottom(),
        )

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = round(
            self.blockBoundingGeometry(block)
            .translated(self.contentOffset())
            .top()
        )
        bottom = top + round(self.blockBoundingRect(block).height())
        current_block = self.textCursor().blockNumber()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(QColor(
                    active_accent_color()
                    if block_number == current_block
                    else OVERLAY_0
                ))
                painter.drawText(
                    0,
                    top,
                    self.line_number_area.width() - 7,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    str(block_number + 1),
                )

            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            block_number += 1

    def _highlight_current_line(self):
        selection = QTextEdit.ExtraSelection()
        selection.format.setBackground(QColor(SURFACE_0))
        selection.format.setProperty(
            QTextFormat.Property.FullWidthSelection,
            True,
        )
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        self.setExtraSelections((selection,))
        self.line_number_area.update()
