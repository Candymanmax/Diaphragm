"""Unsaved-script confirmation dialog."""

from PySide6.QtWidgets import QDialog

from harness_ui.dialogs.app_dialog import AppDialog
from harness_ui.theme import YELLOW


class UnsavedScriptDialog(AppDialog):
    """Frameless confirmation used when an in-memory script is discarded."""

    def __init__(self, parent=None):
        super().__init__(
            "Unsaved script",
            "This script has not been saved. Exit and discard it?",
            parent=parent,
            icon_name="triangle-alert",
            icon_color=YELLOW,
            primary_text="Go back",
            primary_role="primary",
            secondary_text="Exit",
            secondary_role="danger",
            default_action="primary",
            button_order=("primary", "secondary"),
            primary_accepts=False,
            secondary_rejects=False,
            object_name="unsavedScriptDialog",
            panel_object_name="unsavedScriptPanel",
            icon_object_name="unsavedScriptIcon",
            title_object_name="unsavedScriptTitle",
            message_object_name="unsavedScriptMessage",
            primary_object_name="unsavedScriptGoBack",
            secondary_object_name="unsavedScriptExit",
        )
        self.go_back_button = self.primary_button
        self.exit_button = self.secondary_button
        self.go_back_button.clicked.connect(self.reject)
        self.exit_button.clicked.connect(self.accept)
        self.exit_button.setAccessibleName("Exit without saving")

    @classmethod
    def confirm(cls, parent=None):
        dialog = cls(parent)
        return dialog.exec_dialog() == QDialog.DialogCode.Accepted
