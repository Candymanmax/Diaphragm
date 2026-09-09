"""Reusable rounded-card dialogs for confirmations and app messages."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from harness_ui.dialogs.surfaces import RoundedDialogPanel
from harness_ui.icons import lucide_icon
from harness_ui.theme import (
    BLUE,
    BASE,
    COMPACT_SPACING,
    CONTROL_SPACING,
    DIALOG_SPACING,
    INLINE_SPACING,
    RED,
    SKY,
    YELLOW,
    standard_button,
)


class AppDialog(QDialog):
    """A consistent modal card used for confirmations and short messages.

    The component deliberately exposes action labels instead of generic
    confirmation wording. Callers can use the class
    methods for common message types or configure the constructor for a
    specialised prompt while retaining the same layout and keyboard behavior.
    """

    def __init__(
        self,
        title,
        message,
        *,
        parent=None,
        icon_name="info",
        icon_color=BLUE,
        primary_text="Close",
        primary_role="primary",
        secondary_text=None,
        secondary_role="neutral",
        default_action="primary",
        button_order=("secondary", "primary"),
        extra_content=None,
        focus_widget=None,
        primary_accepts=True,
        secondary_rejects=True,
        translucent_background=True,
        delete_on_close=True,
        object_name="appDialog",
        panel_object_name="appDialogPanel",
        icon_object_name="appDialogIcon",
        title_object_name="appDialogTitle",
        message_object_name="appDialogMessage",
        primary_object_name="appDialogPrimary",
        secondary_object_name="appDialogSecondary",
        minimum_width=430,
    ):
        super().__init__(parent)
        self.setObjectName(str(object_name))
        self.setWindowTitle(str(title))
        self.setModal(True)
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            bool(translucent_background),
        )
        self.setAttribute(
            Qt.WidgetAttribute.WA_DeleteOnClose,
            bool(delete_on_close),
        )
        if not translucent_background:
            palette = self.palette()
            palette.setColor(self.backgroundRole(), QColor(BASE))
            self.setPalette(palette)
            self.setAutoFillBackground(True)
        self.setMinimumWidth(int(minimum_width))

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(1, 1, 1, 1)

        panel = RoundedDialogPanel()
        panel.setObjectName(str(panel_object_name))
        outer_layout.addWidget(panel)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 18, 18, 16)
        layout.setSpacing(DIALOG_SPACING)

        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(INLINE_SPACING)

        icon_label = QLabel()
        icon_label.setObjectName(str(icon_object_name))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setFixedSize(34, 34)
        icon_label.setPixmap(
            lucide_icon(str(icon_name), color=icon_color, size=22).pixmap(22, 22)
        )

        copy_layout = QVBoxLayout()
        copy_layout.setContentsMargins(0, 0, 0, 0)
        copy_layout.setSpacing(COMPACT_SPACING)
        title_label = QLabel(str(title))
        title_label.setObjectName(str(title_object_name))
        message_label = QLabel(str(message))
        message_label.setObjectName(str(message_object_name))
        message_label.setWordWrap(True)
        message_label.setTextFormat(Qt.TextFormat.PlainText)
        message_label.setMaximumWidth(620)
        self.title_label = title_label
        self.message_label = message_label
        copy_layout.addWidget(title_label)
        copy_layout.addWidget(message_label)
        if extra_content is not None:
            copy_layout.addWidget(extra_content)

        content_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)
        content_layout.addLayout(copy_layout, 1)
        layout.addLayout(content_layout)

        self.primary_button = standard_button(
            str(primary_text),
            role=primary_role,
            parent=self,
            object_name=primary_object_name,
            accessible_name=str(primary_text),
        )
        if primary_accepts:
            self.primary_button.clicked.connect(self.accept)

        self.secondary_button = None
        if secondary_text is not None:
            self.secondary_button = standard_button(
                str(secondary_text),
                role=secondary_role,
                parent=self,
                object_name=secondary_object_name,
                accessible_name=str(secondary_text),
            )
            if secondary_rejects:
                self.secondary_button.clicked.connect(self.reject)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(CONTROL_SPACING)
        button_layout.addStretch(1)
        buttons = {
            "primary": self.primary_button,
            "secondary": self.secondary_button,
        }
        for name in button_order:
            button = buttons.get(name)
            if button is not None:
                button_layout.addWidget(button)
        layout.addLayout(button_layout)

        self._default_button = (
            self.primary_button
            if default_action == "primary" or self.secondary_button is None
            else self.secondary_button
        )
        self._focus_widget = focus_widget or self._default_button
        self._default_button.setDefault(True)
        self._default_button.setAutoDefault(True)
        for button in (self.primary_button, self.secondary_button):
            if button is not None and button is not self._default_button:
                button.setAutoDefault(False)

    def exec_dialog(self):
        """Center, focus, and execute the modal card."""

        self.adjustSize()
        self.center_on_window(self, self.parentWidget())
        self.raise_()
        self.activateWindow()
        self._focus_widget.setFocus()
        return self.exec()

    @staticmethod
    def center_on_window(widget, reference=None):
        """Center a window on its owning top-level window or screen."""

        reference_window = (
            reference.window() if reference is not None else None
        )
        if reference_window is widget:
            reference_window = None

        if reference_window is None:
            active_window = QApplication.activeWindow()
            if active_window is not widget:
                reference_window = active_window

        if reference_window is not None:
            center = reference_window.frameGeometry().center()
        else:
            screen = widget.screen() or QApplication.primaryScreen()
            if screen is None:
                return
            center = screen.availableGeometry().center()

        widget.move(center - widget.rect().center())

    @classmethod
    def confirm(
        cls,
        parent,
        title,
        message,
        *,
        confirm_text="Continue",
        cancel_text="Cancel",
        confirm_role="primary",
        default_action="secondary",
        icon_name="info",
        icon_color=BLUE,
    ):
        """Show a two-action prompt and return whether it was confirmed."""

        dialog = cls(
            title,
            message,
            parent=parent,
            icon_name=icon_name,
            icon_color=icon_color,
            primary_text=confirm_text,
            primary_role=confirm_role,
            secondary_text=cancel_text,
            secondary_role="neutral",
            default_action=default_action,
        )
        return dialog.exec_dialog() == QDialog.DialogCode.Accepted

    @classmethod
    def get_text(
        cls,
        parent,
        title,
        message,
        *,
        label_text="",
        default_text="",
        placeholder_text="",
        echo_mode=QLineEdit.EchoMode.Normal,
        input_object_name="appDialogTextInput",
        input_accessible_name="Text input",
        confirm_text="Save",
        cancel_text="Cancel",
        confirm_role="primary",
        icon_name="info",
        icon_color=BLUE,
    ):
        """Show a card with a single text field and return its value."""

        form = QWidget()
        form.setObjectName("appDialogInputForm")
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(COMPACT_SPACING)

        if label_text:
            label = QLabel(str(label_text))
            label.setObjectName("appDialogInputLabel")
            form_layout.addWidget(label)

        input_widget = QLineEdit()
        input_widget.setObjectName(str(input_object_name))
        input_widget.setText(str(default_text))
        input_widget.setPlaceholderText(str(placeholder_text))
        input_widget.setEchoMode(echo_mode)
        input_widget.setAccessibleName(str(input_accessible_name))
        form_layout.addWidget(input_widget)

        dialog = cls(
            title,
            message,
            parent=parent,
            icon_name=icon_name,
            icon_color=icon_color,
            primary_text=confirm_text,
            primary_role=confirm_role,
            secondary_text=cancel_text,
            secondary_role="neutral",
            default_action="primary",
            extra_content=form,
            focus_widget=input_widget,
            delete_on_close=False,
        )
        input_widget.returnPressed.connect(dialog.accept)
        accepted = dialog.exec_dialog() == QDialog.DialogCode.Accepted
        value = input_widget.text()
        input_widget.clear()
        dialog.deleteLater()
        return value, accepted

    @classmethod
    def _show_message(
        cls,
        parent,
        title,
        message,
        *,
        icon_name,
        icon_color,
        button_text="Close",
    ):
        dialog = cls(
            title,
            message,
            parent=parent,
            icon_name=icon_name,
            icon_color=icon_color,
            primary_text=button_text,
            primary_role="primary",
        )
        dialog.exec_dialog()

    @classmethod
    def information(cls, parent, title, message):
        """Show an information-style modal card."""

        return cls._show_message(
            parent,
            title,
            message,
            icon_name="info",
            icon_color=SKY,
        )

    @classmethod
    def warning(cls, parent, title, message):
        """Show a warning-style modal card."""

        return cls._show_message(
            parent,
            title,
            message,
            icon_name="triangle-alert",
            icon_color=YELLOW,
        )

    @classmethod
    def critical(cls, parent, title, message):
        """Show an error-style modal card."""

        return cls._show_message(
            parent,
            title,
            message,
            icon_name="triangle-alert",
            icon_color=RED,
        )


__all__ = ("AppDialog",)
