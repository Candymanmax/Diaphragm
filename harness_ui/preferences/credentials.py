"""Secure Hugging Face credential UI behavior."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QLineEdit

from harness_ui.dialogs import AppDialog
from harness_ui.preferences.common import set_feedback
from harness_ui.preferences.workers import _TokenVerifyTask
from modules.app_settings import CredentialStoreError


@dataclass(frozen=True)
class CredentialPreferencesSnapshot:
    """Non-secret credential state safe to expose to observers."""

    configured: bool
    available: bool
    verification_running: bool


class CredentialPreferencesController(QObject):
    """Manage secure token state without exposing token contents."""

    snapshotChanged = Signal(object)

    def __init__(self, *, dialog, credential_store, task_registry):
        super().__init__(dialog)
        self.dialog = dialog
        self.credential_store = credential_store
        self.task_registry = task_registry
        self._configured = False
        self._available = True
        self._verification_running = False

    def snapshot(self):
        return CredentialPreferencesSnapshot(
            configured=self._configured,
            available=self._available,
            verification_running=self._verification_running,
        )

    def _publish_snapshot(self):
        self.snapshotChanged.emit(self.snapshot())

    def connect(self):
        self.dialog.set_token_button.clicked.connect(self.set_token)
        self.dialog.verify_token_button.clicked.connect(self.verify_token)
        self.dialog.clear_token_button.clicked.connect(self.clear_token)

    def refresh_status(self):
        try:
            configured = self.credential_store.has_token()
            self._configured = bool(configured)
            self._available = True
            self.set_status(
                "Configured" if configured else "Not configured",
                "configured" if configured else "unconfigured",
            )
            self.dialog.verify_token_button.setEnabled(configured)
            self.dialog.clear_token_button.setEnabled(configured)
        except CredentialStoreError as error:
            self._configured = False
            self._available = False
            self.set_status("Unavailable", "error")
            self.dialog.verify_token_button.setEnabled(False)
            self.dialog.clear_token_button.setEnabled(False)
            set_feedback(
                self.dialog.credentials_feedback,
                str(error),
                error=True,
            )

        self._publish_snapshot()

    def set_status(self, text, state):
        label = self.dialog.token_status
        label.setText(str(text))
        label.setProperty("credentialState", str(state))
        label.style().unpolish(label)
        label.style().polish(label)

    def set_token(self):
        token, accepted = AppDialog.get_text(
            self.dialog,
            "Hugging Face token",
            "Enter your access token. It will be stored securely in Windows "
            "Credential Manager.",
            label_text="Access token",
            placeholder_text="hf_…",
            echo_mode=QLineEdit.EchoMode.Password,
            input_accessible_name="Hugging Face access token",
            confirm_text="Save token",
            cancel_text="Cancel",
        )

        if not accepted:
            return

        try:
            self.credential_store.set_token(token)
        except CredentialStoreError as error:
            set_feedback(
                self.dialog.credentials_feedback,
                str(error),
                error=True,
            )
            return

        set_feedback(
            self.dialog.credentials_feedback,
            "Token saved in Windows Credential Manager.",
        )
        self.refresh_status()

    def clear_token(self):
        if not AppDialog.confirm(
            self.dialog,
            "Clear Hugging Face token",
            "Remove the saved token from Windows Credential Manager?",
            confirm_text="Clear token",
            cancel_text="Keep token",
            confirm_role="danger",
            default_action="secondary",
        ):
            return

        try:
            self.credential_store.clear_token()
        except CredentialStoreError as error:
            set_feedback(
                self.dialog.credentials_feedback,
                str(error),
                error=True,
            )
            return

        set_feedback(self.dialog.credentials_feedback, "Saved token removed.")
        self.refresh_status()

    def verify_token(self):
        try:
            token = self.credential_store.token()
        except CredentialStoreError as error:
            set_feedback(
                self.dialog.credentials_feedback,
                str(error),
                error=True,
            )
            return

        if not token:
            set_feedback(
                self.dialog.credentials_feedback,
                "No Hugging Face token is configured.",
                error=True,
            )
            return

        self._verification_running = True
        self.dialog.verify_token_button.setEnabled(False)
        set_feedback(self.dialog.credentials_feedback, "Verifying token…")
        thread = QThread(self.dialog)
        task = _TokenVerifyTask(token)
        task.moveToThread(thread)
        thread.started.connect(task.run)
        task.succeeded.connect(
            lambda message: set_feedback(
                self.dialog.credentials_feedback,
                message,
            )
        )
        task.failed.connect(
            lambda message: set_feedback(
                self.dialog.credentials_feedback,
                message,
                error=True,
            )
        )
        task.finished.connect(thread.quit)
        task.finished.connect(task.deleteLater)
        thread.finished.connect(self._verification_finished)
        self.task_registry.add(thread, task)
        thread.start()
        self._publish_snapshot()

    def _verification_finished(self):
        self._verification_running = False
        self.refresh_status()


__all__ = (
    "CredentialPreferencesController",
    "CredentialPreferencesSnapshot",
)
