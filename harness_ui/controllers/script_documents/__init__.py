"""Script-document controller package with stable public imports."""

# The file picker remains available at the package boundary for callers that
# patch file-selection behavior in integration tests.
from PySide6.QtWidgets import QFileDialog

from harness_ui.controllers.script_documents.controller import (
    ScriptDocumentController,
)
from harness_ui.controllers.script_documents.state import (
    SCRIPT_TEXT_ROLE,
    ScriptDocumentSnapshot,
)

__all__ = [
    "QFileDialog",
    "SCRIPT_TEXT_ROLE",
    "ScriptDocumentController",
    "ScriptDocumentSnapshot",
]
