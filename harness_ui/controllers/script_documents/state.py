"""Typed state published by the script-document controller."""

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt


SCRIPT_TEXT_ROLE = int(Qt.ItemDataRole.UserRole) + 1


@dataclass(frozen=True)
class ScriptDocumentSnapshot:
    """Immutable script state published to interested UI components."""

    current_path: Path | None
    dirty: bool
    loading: bool
    total_documents: int
    selected_documents: int
    has_current_document: bool
    has_unsaved_documents: bool
    word_count: int
    character_count: int
