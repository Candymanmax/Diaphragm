"""Composed Preferences window for application-level configuration."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QDialog

from harness_ui.preferences.common import set_feedback
from harness_ui.preferences.credentials import CredentialPreferencesController
from harness_ui.preferences.pages import PreferencesPageBuilder
from harness_ui.preferences.storage import StoragePreferencesController
from harness_ui.preferences.task_registry import PreferenceTaskRegistry
from harness_ui.preferences.values import PreferenceValuesController
from modules.app_settings import CredentialStore, DiagnosticLogStore


class PreferencesDialog(QDialog):
    """Single-window application preferences with immediate persistence."""

    accentChanged = Signal(str)
    lineNumbersChanged = Signal(bool)
    panelVisibilityChanged = Signal(str, bool)
    layoutResetRequested = Signal()
    restartRequired = Signal(str)
    modelsChanged = Signal()

    PAGE_NAMES = (
        "General",
        "Appearance",
        "Library",
        "Models",
        "Storage",
        "Credentials",
        "Updates",
    )

    def __init__(
        self,
        repository,
        service,
        *,
        log_store=None,
        credential_store=None,
        worker_running=None,
        model_busy=None,
        parent=None,
    ):
        super().__init__(parent)
        self.repository = repository
        self.service = service
        self.credential_store = credential_store or CredentialStore()
        self.log_store = log_store or DiagnosticLogStore(repository.paths)
        self.worker_running = worker_running or (lambda: False)
        self.model_busy = model_busy or (lambda: False)
        self._close_pending = False
        self.setObjectName("preferencesDialog")
        self.setWindowTitle("Preferences")
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setModal(False)
        self.resize(940, 680)
        self.setMinimumSize(820, 580)

        self.page_builder = PreferencesPageBuilder(self)
        self.page_builder.build()
        self.task_registry = PreferenceTaskRegistry(self)
        self.storage_controller = StoragePreferencesController(
            dialog=self,
            repository=self.repository,
            service=self.service,
            log_store=self.log_store,
            worker_running=lambda: self.worker_running() or self.model_busy(),
            task_registry=self.task_registry,
        )
        self.credentials_controller = CredentialPreferencesController(
            dialog=self,
            credential_store=self.credential_store,
            task_registry=self.task_registry,
        )
        self.values_controller = PreferenceValuesController(
            dialog=self,
            repository=self.repository,
            log_store=self.log_store,
            refresh_paths=self.storage_controller.refresh_paths,
            refresh_credentials=self.credentials_controller.refresh_status,
        )
        self.task_registry.allFinished.connect(self._finish_pending_close)
        self.values_controller.load()
        self.values_controller.connect()
        self.storage_controller.connect()
        self.credentials_controller.connect()
        self.storage_controller.refresh_usage()

    @property
    def background_tasks(self):
        return self.task_registry.entries

    @property
    def migration_active(self):
        return self.storage_controller.migration_active

    def refresh_usage(self):
        self.storage_controller.refresh_usage()

    def closeEvent(self, event):
        if self.model_manager.busy:
            set_feedback(
                self.models_feedback,
                "Wait for the model operation to finish before closing Preferences.",
                error=True,
            )
            event.ignore()
            return

        if self.storage_controller.migration_active:
            set_feedback(
                self.library_feedback,
                "Wait for the verified copy to finish before closing Preferences.",
                error=True,
            )
            event.ignore()
            return

        if self.task_registry.has_running_tasks():
            self._close_pending = True
            self.hide()
            event.ignore()
            return

        super().closeEvent(event)
        self.deleteLater()

    def _finish_pending_close(self):
        if self._close_pending and not self.task_registry.has_running_tasks():
            self._close_pending = False
            QTimer.singleShot(0, self.close)

    def showEvent(self, event):
        self._close_pending = False
        self.model_manager.refresh_inventory()
        super().showEvent(event)

    def prepare_for_application_exit(self, timeout_ms=5000):
        if self.storage_controller.migration_active or self.model_manager.busy:
            return False

        return self.task_registry.stop_all(timeout_ms)


__all__ = ("PreferencesDialog",)
