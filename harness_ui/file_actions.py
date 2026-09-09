"""Safe filesystem actions initiated by the desktop interface."""

from __future__ import annotations

import os
from pathlib import Path
import uuid

from PySide6.QtCore import QFile


def atomic_write_text(path, text):
    """Write UTF-8 text through an adjacent temporary file."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"

    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as file:
            file.write(text)
            file.flush()
            os.fsync(file.fileno())

        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def move_to_trash(path):
    """Move one user-selected file to the platform Recycle Bin."""

    result = QFile.moveToTrash(str(path))
    return result[0] if isinstance(result, tuple) else bool(result)


__all__ = ("atomic_write_text", "move_to_trash")
