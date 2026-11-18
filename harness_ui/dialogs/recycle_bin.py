"""Recycle-bin confirmation dialog."""

from PySide6.QtWidgets import QDialog

from harness_ui.dialogs.app_dialog import AppDialog
from harness_ui.theme import RED
from modules.platform_support import trash_name


class RecycleBinDialog(AppDialog):
    """Frameless confirmation used before moving a script to the Recycle Bin."""

    def __init__(self, filename, detail="", parent=None):
        super().__init__(
            f"Move script to {trash_name()}",
            f"Move '{filename}' to the {trash_name()}?{detail}",
            parent=parent,
            icon_name="trash-2",
            icon_color=RED,
            primary_text=f"Move to {trash_name()}",
            primary_role="danger",
            secondary_text="Cancel",
            secondary_role="neutral",
            default_action="secondary",
            object_name="recycleBinDialog",
            panel_object_name="recycleBinPanel",
            icon_object_name="recycleBinIcon",
            title_object_name="recycleBinTitle",
            message_object_name="recycleBinMessage",
            primary_object_name="recycleBinConfirm",
            secondary_object_name="recycleBinCancel",
        )
        self.cancel_button = self.secondary_button
        self.confirm_button = self.primary_button
        self.cancel_button.setAccessibleName("Cancel moving script")
        self.confirm_button.setAccessibleName(f"Move script to {trash_name()}")

    @classmethod
    def confirm(cls, parent=None, filename="", detail=""):
        dialog = cls(filename, detail, parent)
        return dialog.exec_dialog() == QDialog.DialogCode.Accepted


__all__ = ("RecycleBinDialog",)
