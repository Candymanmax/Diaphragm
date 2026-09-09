from __future__ import annotations

import html
import sys
import textwrap

from PySide6.QtCore import (
    QEvent,
    QObject,
    QPoint,
    QProcess,
    QRectF,
    QTimer,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractScrollArea,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStyle,
    QStyleOptionComboBox,
    QStyleOptionSpinBox,
    QToolBox,
    QVBoxLayout,
    QWidget,
)

from modules.adapters.registry import (
    GENERATION_CONTROL_LABELS,
    GENERATION_CONTROL_NAMES,
    LANGUAGE_NAMES,
    MODEL_ADAPTER_NAMES,
    get_model_capabilities,
    model_is_installed,
)
from modules.config import GENERATION_CONTROL_LIMITS, PipelineConfig
from harness_ui.icons import lucide_icon
from harness_ui.theme import (
    active_accent_color,
    MANTLE,
    SUBTEXT_0,
    SURFACE_1,
    set_button_role,
)

GENERATION_PRESETS = {
    "Balanced": {
        "exaggeration": 0.60,
        "cfg_weight": 0.40,
        "temperature": 0.80,
        "repetition_penalty": 1.20,
        "min_p": 0.05,
        "top_p": 1.00,
    },
    "Seductive": {
        "exaggeration": 0.70,
        "cfg_weight": 0.30,
        "temperature": 0.70,
        "repetition_penalty": 1.20,
        "min_p": 0.05,
        "top_p": 0.90,
    },
}

GENERATION_CONTROL_HELP = {
    "exaggeration": (
        "How strongly the voice emphasizes emotion and expression. "
        "Higher values sound more dramatic."
    ),
    "cfg_weight": (
        "How strongly generation follows its conditioning. Lower values "
        "allow looser pacing; higher values can sound more constrained."
    ),
    "temperature": (
        "How much the delivery can vary. Lower values are steadier; "
        "higher values are less predictable."
    ),
    "repetition_penalty": (
        "How strongly repeated sounds and words are discouraged. "
        "Higher values apply more prevention."
    ),
    "min_p": (
        "Filters out choices that are much less likely than the best current "
        "choice. Higher values are more restrictive."
    ),
    "top_p": (
        "Restricts generation to a range of likely choices. Lower values "
        "are more consistent; 1.00 keeps the full range."
    ),
    "top_k": (
        "The maximum number of likely choices considered at each step. "
        "Lower values make delivery more predictable."
    ),
}


def _inspector_model_label(model_id):
    capability = get_model_capabilities(model_id)
    return (
        "Original"
        if capability.model_id == "original"
        else capability.display_name
    )


def _generation_help_tooltip(label, description, minimum, maximum):
    wrapped = "<br>".join(
        html.escape(line)
        for line in textwrap.wrap(str(description), width=52)
    )
    return (
        '<div style="white-space: nowrap">'
        f"<b>{html.escape(str(label))}</b><br>"
        f"{wrapped}<br><br>"
        f'<span style="color: {SUBTEXT_0}">'
        f"Allowed range: {minimum:g}–{maximum:g}"
        "</span></div>"
    )


def _forward_wheel_to_scroll_area(widget, event):
    ancestor = widget.parentWidget()

    while ancestor is not None:
        if isinstance(ancestor, QAbstractScrollArea):
            ancestor.wheelEvent(event)
            return

        ancestor = ancestor.parentWidget()

    event.ignore()


class _SmoothTooltip(QFrame):
    """A single tooltip window that gently follows a moving pointer."""

    WIDTH = 300
    HORIZONTAL_PADDING = 11
    VERTICAL_PADDING = 9
    FOLLOW_INTERVAL_MS = 16
    FOLLOW_FACTOR = 0.32
    CORNER_RADIUS = 8

    def __init__(self, parent):
        flags = (
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
        )
        super().__init__(parent, flags)
        self.setObjectName("generationHelpTooltip")
        self.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(self.WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            self.HORIZONTAL_PADDING,
            self.VERTICAL_PADDING,
            self.HORIZONTAL_PADDING,
            self.VERTICAL_PADDING,
        )
        self.text_label = QLabel()
        self.text_label.setObjectName("generationHelpTooltipText")
        self.text_label.setTextFormat(Qt.TextFormat.RichText)
        self.text_label.setWordWrap(True)
        self.text_label.setFixedWidth(
            self.WIDTH - (self.HORIZONTAL_PADDING * 2)
        )
        layout.addWidget(self.text_label)

        self._target_position = QPoint()
        self._follow_timer = QTimer(self)
        self._follow_timer.setInterval(self.FOLLOW_INTERVAL_MS)
        self._follow_timer.timeout.connect(self._advance_position)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor(SURFACE_1), 1))
        painter.setBrush(QColor(MANTLE))
        bounds = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        painter.drawRoundedRect(
            bounds,
            self.CORNER_RADIUS,
            self.CORNER_RADIUS,
        )
        painter.end()

    def show_tip(self, text, position):
        self.text_label.setText(text)
        content_height = self.text_label.heightForWidth(
            self.text_label.width()
        )
        if content_height < 0:
            content_height = self.text_label.sizeHint().height()
        self.text_label.setFixedHeight(content_height)
        self.setFixedHeight(content_height + (self.VERTICAL_PADDING * 2))
        self._target_position = QPoint(position)
        self._follow_timer.stop()
        self.move(position)
        self.show()
        self.raise_()

    def follow(self, position):
        self._target_position = QPoint(position)
        if self.isVisible() and not self._follow_timer.isActive():
            self._follow_timer.start()

    def hide_tip(self):
        self._follow_timer.stop()
        self.hide()

    @staticmethod
    def _smoothed_coordinate(current, target):
        distance = target - current
        if abs(distance) <= 1:
            return target

        step = round(distance * _SmoothTooltip.FOLLOW_FACTOR)
        if step == 0:
            step = 1 if distance > 0 else -1
        return current + step

    def _advance_position(self):
        current = self.pos()
        target = self._target_position
        next_position = QPoint(
            self._smoothed_coordinate(current.x(), target.x()),
            self._smoothed_coordinate(current.y(), target.y()),
        )
        self.move(next_position)

        if next_position == target:
            self._follow_timer.stop()


class _LeftTooltipFilter(QObject):
    """Show inspector help to the left and smoothly follow the cursor."""

    TOOLTIP_WIDTH = _SmoothTooltip.WIDTH
    CURSOR_GAP = 18
    VERTICAL_OFFSET = 12

    def __init__(self, panel):
        super().__init__(panel)
        self.panel = panel
        self.tooltip = _SmoothTooltip(panel)
        self._active_widget = None

    def _target_position(self, global_position):
        return QPoint(
            global_position.x() - self.TOOLTIP_WIDTH - self.CURSOR_GAP,
            global_position.y() + self.VERTICAL_OFFSET,
        )

    def eventFilter(self, watched, event):
        if (
            event.type() == QEvent.Type.ToolTip
            and watched.toolTip()
        ):
            target_position = self._target_position(event.globalPos())
            if (
                watched is self._active_widget
                and self.tooltip.isVisible()
            ):
                self.tooltip.follow(target_position)
                return True

            self._active_widget = watched
            self.tooltip.show_tip(
                watched.toolTip(),
                target_position,
            )
            return True

        if (
            event.type() == QEvent.Type.MouseMove
            and watched is self._active_widget
            and self.tooltip.isVisible()
        ):
            self.tooltip.follow(
                self._target_position(event.globalPosition().toPoint())
            )

        if (
            event.type() == QEvent.Type.Leave
            and watched is self._active_widget
        ):
            self.tooltip.hide_tip()
            self._active_widget = None

        return super().eventFilter(watched, event)


class NoWheelComboBox(QComboBox):
    """Keep the mouse wheel inert while the pointer is over a setting."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    def setEditable(self, editable):
        super().setEditable(editable)
        if editable and self.lineEdit() is not None:
            self.lineEdit().setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    def wheelEvent(self, event):
        _forward_wheel_to_scroll_area(self, event)

    def paintEvent(self, event):
        super().paintEvent(event)

        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        rect = self.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            option,
            QStyle.SubControl.SC_ComboBoxArrow,
            self,
        )
        if not rect.isValid():
            return

        is_pressed = bool(
            option.state & QStyle.StateFlag.State_Sunken
        ) and bool(
            option.activeSubControls
            & QStyle.SubControl.SC_ComboBoxArrow
        )
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        lucide_icon(
            "chevron-down",
            color=(active_accent_color() if is_pressed else SUBTEXT_0),
            size=10,
        ).paint(
            painter,
            rect,
            Qt.AlignmentFlag.AlignCenter,
        )
        painter.end()


class ModelComboBox(NoWheelComboBox):
    aboutToShowPopup = Signal()

    def showPopup(self):
        self.aboutToShowPopup.emit()
        super().showPopup()


class _NoWheelSpinMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    def wheelEvent(self, event):
        _forward_wheel_to_scroll_area(self, event)

    def paintEvent(self, event):
        super().paintEvent(event)

        option = QStyleOptionSpinBox()
        self.initStyleOption(option)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        for control, icon_name in (
            (QStyle.SubControl.SC_SpinBoxUp, "chevron-up"),
            (QStyle.SubControl.SC_SpinBoxDown, "chevron-down"),
        ):
            rect = self.style().subControlRect(
                QStyle.ComplexControl.CC_SpinBox,
                option,
                control,
                self,
            )
            if rect.isValid():
                is_pressed = bool(
                    option.state & QStyle.StateFlag.State_Sunken
                ) and bool(option.activeSubControls & control)
                lucide_icon(
                    icon_name,
                    color=(active_accent_color() if is_pressed else SUBTEXT_0),
                    size=10,
                ).paint(
                    painter,
                    rect,
                    Qt.AlignmentFlag.AlignCenter,
                )

        painter.end()


class NoWheelSpinBox(_NoWheelSpinMixin, QSpinBox):
    pass


class NoWheelDoubleSpinBox(_NoWheelSpinMixin, QDoubleSpinBox):
    pass


def _integer(minimum, maximum, step=1, suffix=""):
    widget = NoWheelSpinBox()
    widget.setRange(minimum, maximum)
    widget.setSingleStep(step)
    widget.setSuffix(suffix)
    return widget


def _decimal(minimum, maximum, step, decimals=2, suffix=""):
    widget = NoWheelDoubleSpinBox()
    widget.setRange(minimum, maximum)
    widget.setSingleStep(step)
    widget.setDecimals(decimals)
    widget.setSuffix(suffix)
    return widget
