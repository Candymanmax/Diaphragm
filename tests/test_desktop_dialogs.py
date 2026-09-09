"""Regression tests for the shared application dialog component."""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLineEdit,
    QPushButton,
    QWidget,
)

from harness_ui.dialogs import (
    AppDialog,
    RecycleBinDialog,
    RuntimeSetupDialog,
    UnsavedScriptDialog,
)
from modules.runtime_manager import (
    CPU_RUNTIME,
    RUNTIME_ARCHITECTURE_BITS,
    RUNTIME_PYTHON_VERSION,
    PythonCommand,
    RuntimeManager,
)


class AppDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def test_confirmation_uses_explicit_actions_and_safe_default(self):
        state = {}

        def inspect_dialog():
            dialog = self.application.activeModalWidget()
            state["object_name"] = dialog.objectName()
            state["buttons"] = [
                button.text()
                for button in dialog.findChildren(QPushButton)
            ]
            state["default"] = dialog.focusWidget().text()
            dialog.secondary_button.click()

        QTimer.singleShot(0, inspect_dialog)
        self.assertFalse(
            AppDialog.confirm(
                None,
                "Delete item",
                "Move this item to the Recycle Bin?",
                confirm_text="Move to Recycle Bin",
                cancel_text="Cancel",
                confirm_role="danger",
                default_action="secondary",
            )
        )
        self.assertEqual(state["object_name"], "appDialog")
        self.assertEqual(state["buttons"], ["Cancel", "Move to Recycle Bin"])
        self.assertEqual(state["default"], "Cancel")

    def test_existing_confirmation_cards_reuse_the_component(self):
        recycle = RecycleBinDialog("script.txt")
        unsaved = UnsavedScriptDialog()
        try:
            self.assertIsInstance(recycle, AppDialog)
            self.assertIsInstance(unsaved, AppDialog)
            self.assertEqual(recycle.confirm_button.text(), "Move to Recycle Bin")
            self.assertEqual(unsaved.go_back_button.text(), "Go back")
        finally:
            recycle.close()
            unsaved.close()

    def test_text_entry_uses_the_same_card_and_returns_the_value(self):
        state = {}

        def complete_dialog():
            dialog = self.application.activeModalWidget()
            input_widget = dialog.findChild(QLineEdit, "appDialogTextInput")
            state["object_name"] = dialog.objectName()
            state["focused"] = dialog.focusWidget() is input_widget
            input_widget.setText("private-token")
            dialog.primary_button.click()

        QTimer.singleShot(0, complete_dialog)
        value, accepted = AppDialog.get_text(
            None,
            "Hugging Face token",
            "Enter an access token.",
            label_text="Access token",
            echo_mode=QLineEdit.EchoMode.Password,
            confirm_text="Save token",
        )

        self.assertTrue(accepted)
        self.assertEqual(value, "private-token")
        self.assertEqual(state["object_name"], "appDialog")
        self.assertTrue(state["focused"])

    def test_modal_card_centers_on_the_top_level_owner(self):
        owner = QWidget()
        owner.setGeometry(100, 120, 800, 500)
        owner.show()
        child = QWidget(owner)
        dialog = AppDialog(
            "Install model",
            "Install this model into the cache?",
            parent=child,
            delete_on_close=False,
        )
        state = {}

        def inspect_dialog():
            state["dialog_center"] = dialog.frameGeometry().center()
            state["owner_center"] = owner.frameGeometry().center()
            dialog.accept()

        try:
            QTimer.singleShot(0, inspect_dialog)
            dialog.exec_dialog()
            self.assertEqual(state["dialog_center"], state["owner_center"])
        finally:
            dialog.close()
            owner.close()

    def test_runtime_setup_uses_the_shared_dialog_and_progress_controls(self):
        with TemporaryDirectory() as temporary:
            manager = RuntimeManager(temporary, spec=CPU_RUNTIME)
            dialog = RuntimeSetupDialog(
                manager,
                PythonCommand("python"),
            )
            try:
                dialog.show()
                self.application.processEvents()
                self.assertIsInstance(dialog, AppDialog)
                self.assertEqual(dialog.objectName(), "appDialog")
                self.assertEqual(
                    dialog.progress_bar.objectName(),
                    "runtimeSetupProgress",
                )
                self.assertEqual(dialog.progress_bar.value(), 0)
                self.assertEqual(dialog.primary_button.text(), "Cancel")
                self.assertFalse(dialog.secondary_button.isVisible())
            finally:
                dialog.close()

    def test_runtime_setup_reuses_a_valid_runtime_without_opening_a_dialog(self):
        ready_python = Path("C:/runtime/python.exe")
        manager = Mock()
        manager.ready_python.return_value = ready_python

        with patch(
            "harness_ui.dialogs.runtime_setup.RuntimeManager",
            return_value=manager,
        ):
            result = RuntimeSetupDialog.ensure("C:/app-data")

        self.assertTrue(result.ready)
        self.assertFalse(result.cancelled)
        manager.activate.assert_called_once_with(ready_python)
        manager.bootstrap_command.assert_not_called()

    def test_runtime_setup_advances_through_install_and_verification(self):
        with TemporaryDirectory() as temporary:
            manager = RuntimeManager(temporary, spec=CPU_RUNTIME)
            dialog = RuntimeSetupDialog(
                manager,
                PythonCommand("python"),
            )
            try:
                with patch.object(
                    dialog,
                    "_flush_process_output",
                ), patch.object(dialog, "_start_process") as start_process:
                    dialog._stage = "venv"
                    dialog._process_finished(0, None)
                    self.assertEqual(dialog._stage, "install")
                    start_process.assert_called_once_with(
                        *manager.install_command()
                    )

                    start_process.reset_mock()
                    dialog._process_finished(0, None)
                    self.assertEqual(dialog._stage, "verify")
                    start_process.assert_called_once_with(
                        *manager.verify_command()
                    )

                    start_process.reset_mock()
                    with patch.object(manager, "activate") as activate, patch(
                        "harness_ui.dialogs.runtime_setup.QTimer.singleShot"
                    ) as single_shot:
                        dialog._process_finished(0, None)

                self.assertEqual(dialog._stage, "ready")
                self.assertTrue(dialog.runtime_ready)
                self.assertEqual(dialog.progress_bar.value(), 100)
                activate.assert_called_once_with()
                single_shot.assert_called_once()
                start_process.assert_not_called()
            finally:
                dialog.close()

    def test_runtime_setup_failure_stays_in_the_same_card(self):
        with TemporaryDirectory() as temporary:
            manager = RuntimeManager(temporary, spec=CPU_RUNTIME)
            dialog = RuntimeSetupDialog(manager, None)
            try:
                dialog.show()
                self.application.processEvents()
                dialog._stage = "install"
                dialog._last_output = ["network unavailable"]
                with patch.object(dialog, "_flush_process_output"):
                    dialog._process_finished(1, None)

                self.assertEqual(dialog._stage, "failed")
                self.assertEqual(dialog.primary_button.text(), "Close")
                self.assertTrue(dialog.secondary_button.isVisible())
                self.assertTrue(dialog.secondary_button.isEnabled())
                self.assertIn("runtime", dialog.status_label.text().lower())
                self.assertIn("network unavailable", dialog.detail_label.text())
            finally:
                dialog.close()

    def test_runtime_setup_reports_when_bootstrap_python_is_missing(self):
        with TemporaryDirectory() as temporary:
            manager = RuntimeManager(temporary, spec=CPU_RUNTIME)
            dialog = RuntimeSetupDialog(manager, None)
            try:
                with patch.object(dialog, "_start_process") as start_process:
                    dialog._begin_setup()

                self.assertEqual(dialog._stage, "failed")
                self.assertFalse(dialog.runtime_ready)
                expected_version = ".".join(
                    str(part) for part in RUNTIME_PYTHON_VERSION
                )
                self.assertIn(
                    f"{RUNTIME_ARCHITECTURE_BITS}-bit Python "
                    f"{expected_version}",
                    dialog.status_label.text(),
                )
                self.assertTrue(dialog.secondary_button.isEnabled())
                start_process.assert_not_called()
            finally:
                dialog.close()

    def test_runtime_setup_cancel_stops_the_active_process(self):
        with TemporaryDirectory() as temporary:
            manager = RuntimeManager(temporary, spec=CPU_RUNTIME)
            dialog = RuntimeSetupDialog(
                manager,
                PythonCommand("python"),
            )
            process = Mock()
            process.state.return_value = QProcess.ProcessState.Running
            dialog.process = process
            dialog._stage = "install"

            try:
                dialog.reject()

                self.assertTrue(dialog._cancelled_by_user)
                self.assertIsNone(dialog._stage)
                process.kill.assert_called_once_with()
                process.waitForFinished.assert_called_once_with(2000)
            finally:
                dialog.close()


if __name__ == "__main__":
    unittest.main()
