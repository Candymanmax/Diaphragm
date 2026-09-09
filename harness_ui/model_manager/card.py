from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
)

from harness_ui.theme import CONTROL_SPACING, SECTION_SPACING, standard_button
from modules.adapters.registry import MODEL_DOWNLOAD_FILES, get_model_capabilities


def format_local_size(value):
    value = max(0, int(value))

    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value} {unit}" if unit == "B" else f"{value:.2f} {unit}"
        value /= 1024

    return "0 B"


class ModelCard(QFrame):
    operationRequested = Signal(str, str)

    OPERATION_LABELS = {
        "install": "Installing…",
        "update": "Updating…",
        "verify": "Verifying…",
        "repair": "Repairing…",
        "remove": "Removing…",
    }

    def __init__(self, model_id, parent=None):
        super().__init__(parent)
        self.model_id = str(model_id)
        self.inventory = None
        self.setObjectName("modelManagerCard")
        self.setProperty("modelState", "missing")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(SECTION_SPACING)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        capability = get_model_capabilities(self.model_id)
        self.name_label = QLabel(capability.display_name)
        self.name_label.setObjectName("modelManagerName")
        self.state_badge = QLabel("Not installed")
        self.state_badge.setObjectName("modelManagerStateBadge")
        self.state_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self.name_label)
        header.addStretch(1)
        header.addWidget(self.state_badge)
        layout.addLayout(header)

        repository, _required_files = MODEL_DOWNLOAD_FILES[self.model_id]
        self.repository_label = QLabel(f"{repository} · revision main")
        self.repository_label.setObjectName("modelManagerRepository")
        self.repository_label.setProperty("muted", True)
        layout.addWidget(self.repository_label)

        self.local_size_label = QLabel("Local files: 0 B")
        self.local_size_label.setObjectName("modelManagerLocalSize")
        self.local_size_label.setProperty("muted", True)
        layout.addWidget(self.local_size_label)

        self.status_label = QLabel()
        self.status_label.setObjectName("modelManagerStatus")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setObjectName("modelOperationProgress")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.hide()
        layout.addWidget(self.progress)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(CONTROL_SPACING)
        self.buttons = {}

        for operation, text in (
            ("install", "Install"),
            ("update", "Update"),
            ("verify", "Verify"),
            ("repair", "Repair"),
            ("remove", "Remove"),
        ):
            button = standard_button(
                text,
                role="danger" if operation == "remove" else "neutral",
                parent=self,
                object_name=f"model{operation.title()}Button",
            )
            button.clicked.connect(
                lambda _checked=False, selected=operation: (
                    self.operationRequested.emit(self.model_id, selected)
                )
            )
            self.buttons[operation] = button
            actions.addWidget(button)

        actions.addStretch(1)
        layout.addLayout(actions)

    def set_inventory(self, inventory):
        self.inventory = inventory
        state = inventory.state
        self.setProperty("modelState", state)
        self.state_badge.setProperty("modelState", state)
        self.state_badge.setText({
            "installed": "Installed",
            "unverified": "Installed",
            "partial": "Needs repair",
            "missing": "Not installed",
        }[state])
        self.local_size_label.setText(
            f"Local files: {format_local_size(inventory.local_bytes)}"
        )
        self.status_label.setText(inventory.message)
        self.status_label.setProperty("error", False)
        self._set_button_availability(False)
        self._repolish()
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _set_button_availability(self, busy):
        state = self.inventory.state if self.inventory is not None else "missing"
        available = {
            "install": state == "missing",
            "update": state in {"installed", "unverified"},
            "verify": state in {"installed", "unverified"},
            "repair": state in {"installed", "unverified", "partial"},
            "remove": state != "missing",
        }

        for operation, button in self.buttons.items():
            button.setEnabled(not busy and available[operation])

    def begin_operation(self, operation, active):
        self._set_button_availability(True)

        if not active:
            self.progress.hide()
            return

        self.progress.setValue(0)
        self.progress.setFormat(self.OPERATION_LABELS[operation] + " %p%")
        self.progress.show()
        self.set_operation_message(self.OPERATION_LABELS[operation])

    def set_progress(self, value):
        self.progress.setValue(max(0, min(100, int(value))))

    def set_operation_message(self, message, *, error=False):
        self.status_label.setText(str(message))
        self.status_label.setProperty("error", bool(error))
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def finish_operation(self):
        self.progress.hide()
        self._set_button_availability(False)

    def _repolish(self):
        for widget in (self, self.state_badge):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
