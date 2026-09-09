from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtCore import QProcess, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from harness_ui.dialogs import AppDialog
from modules.adapters.registry import MODEL_ADAPTER_NAMES, get_model_capabilities
from modules.model_inventory import inspect_model_inventory
from modules.model_operations import (
    model_download_arguments,
    model_inventory_arguments,
)
from harness_ui.theme import SECTION_SPACING

from .card import ModelCard


class ModelManagerWidget(QScrollArea):
    """Local model inventory and explicit model-maintenance actions."""

    modelsChanged = Signal()
    operationStateChanged = Signal(bool)

    def __init__(
        self,
        paths,
        install_root,
        *,
        worker_running=None,
        model_busy=None,
        parent=None,
    ):
        super().__init__(parent)
        self.paths = paths
        self.install_root = Path(install_root).resolve()
        self.worker_running = worker_running or (lambda: False)
        self.model_busy = model_busy or (lambda: False)
        self.cards = {}
        self._active_model_id = None
        self._active_operation = None
        self._output_buffer = ""
        self._last_message = ""
        self.setObjectName("modelManagerScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._build_ui()

        self.process = QProcess(self)
        self.process.setProcessChannelMode(
            QProcess.ProcessChannelMode.MergedChannels
        )
        self.process.readyReadStandardOutput.connect(self._read_process_output)
        self.process.finished.connect(self._process_finished)
        self.process.errorOccurred.connect(self._process_error)
        self.refresh_inventory()

    def _build_ui(self):
        content = QWidget()
        content.setObjectName("modelManagerContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(SECTION_SPACING)

        for model_id in MODEL_ADAPTER_NAMES:
            card = ModelCard(model_id)
            card.operationRequested.connect(self.request_operation)
            self.cards[model_id] = card
            layout.addWidget(card)

        layout.addStretch(1)
        self.setWidget(content)

    @property
    def busy(self):
        return self._active_model_id is not None or (
            self.process.state() != QProcess.ProcessState.NotRunning
        )

    def set_paths(self, paths):
        if self.busy:
            return False

        self.paths = paths
        self.refresh_inventory()
        return True

    def refresh_inventory(self):
        for model_id, card in self.cards.items():
            try:
                inventory = inspect_model_inventory(
                    model_id,
                    self.paths.hub_cache_root,
                )
                card.set_inventory(inventory)
            except Exception as error:
                card.set_operation_message(str(error), error=True)

    def request_operation(self, model_id, operation, *, confirm=True):
        model_id = str(model_id)
        operation = str(operation)

        if self.busy:
            return False

        card = self.cards[model_id]

        if self.model_busy():
            card.set_operation_message(
                "Finish the current model operation before changing model files.",
                error=True,
            )
            return False

        if self.worker_running():
            card.set_operation_message(
                "Finish the active generation job before changing model files.",
                error=True,
            )
            return False

        if confirm and not self._confirm_operation(model_id, operation):
            return False

        self._active_model_id = model_id
        self._active_operation = operation
        self._output_buffer = ""
        self._last_message = ""

        for selected_card in self.cards.values():
            selected_card.begin_operation(
                operation,
                selected_card is card,
            )

        self.operationStateChanged.emit(True)
        self.process.setWorkingDirectory(str(self.install_root))
        if operation in {"verify", "remove"}:
            arguments = model_inventory_arguments(
                operation,
                model_id,
                self.paths.hub_cache_root,
            )
        else:
            arguments = model_download_arguments(
                model_id,
                self.paths.hub_cache_root,
                operation,
            )

        self.process.start(sys.executable, arguments)
        return True

    def _confirm_operation(self, model_id, operation):
        name = get_model_capabilities(model_id).display_name
        prompts = {
            "install": (
                "Install model",
                f'Install "{name}" into the model cache?\n\n'
                "This downloads model files from Hugging Face.",
            ),
            "update": (
                "Update model",
                f'Check "{name}" for updated files and download them?\n\n'
                "Existing cached files are kept when they are unchanged.",
            ),
            "repair": (
                "Repair model",
                f'Redownload the files required by "{name}"?\n\n'
                "This can repair missing or damaged cached files.",
            ),
            "remove": (
                "Remove model",
                f'Remove "{name}" from the model cache?\n\n'
                "Scripts, voices, jobs, and generated outputs are not removed.",
            ),
        }

        if operation == "verify":
            return True

        title, message = prompts[operation]
        return AppDialog.confirm(
            self,
            title,
            message,
            confirm_text="Continue",
            cancel_text="Cancel",
            default_action="secondary",
            confirm_role="danger" if operation == "remove" else "primary",
        )

    def _read_process_output(self):
        text = bytes(self.process.readAllStandardOutput()).decode(
            "utf-8",
            errors="replace",
        )
        self._output_buffer += text.replace("\r", "\n")
        lines = self._output_buffer.split("\n")
        self._output_buffer = lines.pop()

        for line in lines:
            self._handle_process_line(line.strip())

    def _handle_process_line(self, line):
        if not line or self._active_model_id is None:
            return

        card = self.cards[self._active_model_id]

        if line.startswith("MODEL_PROGRESS "):
            try:
                card.set_progress(int(line.removeprefix("MODEL_PROGRESS ")))
            except ValueError:
                pass
            return

        if line.startswith("MODEL_MESSAGE "):
            message = line.removeprefix("MODEL_MESSAGE ").strip()
            self._last_message = message
            card.set_operation_message(message)

    def _process_error(self, error):
        if self._active_model_id is not None:
            self.cards[self._active_model_id].set_operation_message(
                "The model operation could not be started.",
                error=True,
            )

        if error == QProcess.ProcessError.FailedToStart:
            self._complete_process(-1)

    def _process_finished(self, exit_code, _exit_status):
        self._complete_process(exit_code)

    def _complete_process(self, exit_code):
        if self._active_model_id is None:
            return

        self._read_process_output()

        if self._output_buffer.strip():
            self._handle_process_line(self._output_buffer.strip())

        model_id = self._active_model_id
        operation = self._active_operation
        self._active_model_id = None
        self._active_operation = None
        self._output_buffer = ""
        self.refresh_inventory()

        if model_id is not None:
            card = self.cards[model_id]
            succeeded = int(exit_code) == 0

            if succeeded:
                message = self._last_message or {
                    "verify": "All required model files passed verification.",
                    "remove": "Local model files removed.",
                }.get(operation, "Model is ready to use.")
                card.set_operation_message(message)
                self.modelsChanged.emit()
            else:
                card.set_operation_message(
                    "The model operation did not complete. Try Repair or "
                    "check the diagnostic output.",
                    error=True,
                )

        for selected_card in self.cards.values():
            selected_card.finish_operation()

        self._last_message = ""
        self.operationStateChanged.emit(False)
