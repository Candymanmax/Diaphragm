"""New-job naming dialog."""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QWidget

from harness_ui.dialogs.app_dialog import AppDialog
from harness_ui.dialogs.surfaces import RoundedJobNameInput
from harness_ui.theme import INLINE_SPACING, TEAL


class NewJobDialog(AppDialog):
    """Frameless job-name prompt with inline validation."""

    def __init__(self, parent=None, default_name="New job"):
        form = QWidget()
        form.setObjectName("newJobForm")
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(INLINE_SPACING)
        self.name_input = RoundedJobNameInput(str(default_name))
        self.name_input.setObjectName("newJobNameInput")
        self.name_input.setPlaceholderText("Job name")
        self.name_input.setAccessibleName("Job name")
        self.validation = QLabel("Enter a job name.")
        self.validation.setObjectName("newJobValidation")
        self.validation.hide()
        form_layout.addWidget(self.name_input)
        form_layout.addWidget(self.validation)

        super().__init__(
            "New TTS job",
            "Choose a name for this job",
            parent=parent,
            icon_name="plus",
            icon_color=TEAL,
            primary_text="Create job",
            primary_role="primary",
            secondary_text="Cancel",
            secondary_role="neutral",
            default_action="primary",
            extra_content=form,
            primary_accepts=False,
            translucent_background=False,
            delete_on_close=False,
            object_name="newJobDialog",
            panel_object_name="newJobPanel",
            icon_object_name="newJobIcon",
            title_object_name="newJobTitle",
            message_object_name="newJobDescription",
            primary_object_name="newJobCreate",
            secondary_object_name="newJobCancel",
            minimum_width=460,
        )
        self.cancel_button = self.secondary_button
        self.create_button = self.primary_button
        self.cancel_button.setAccessibleName("Cancel new job")
        self.create_button.setAccessibleName("Create job")
        self.create_button.clicked.connect(self._submit)
        self.name_input.returnPressed.connect(self._submit)
        self.name_input.textChanged.connect(self.validation.hide)
        QTimer.singleShot(0, self._focus_name)

    def _focus_name(self):
        self.name_input.setFocus()
        self.name_input.selectAll()

    def _submit(self):
        if not self.job_name():
            self.validation.show()
            self.name_input.setFocus()
            return
        self.accept()

    def job_name(self):
        return self.name_input.text().strip()

    @classmethod
    def prompt(cls, parent=None, default_name="New job"):
        dialog = cls(parent, default_name)
        accepted = dialog.exec_dialog() == QDialog.DialogCode.Accepted
        value = dialog.job_name() if accepted else ""
        dialog.deleteLater()
        return value, accepted
