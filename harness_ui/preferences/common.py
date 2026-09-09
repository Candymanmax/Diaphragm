"""Small presentation helpers shared by Preferences controllers."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


def format_size(value):
    value = int(value)

    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.2f} {unit}"

        value /= 1024

    return "0 B"


def set_feedback(label, message, *, error=False):
    label.setText(str(message))
    label.setProperty("error", bool(error))
    label.style().unpolish(label)
    label.style().polish(label)
    label.show()


def open_folder(path):
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


__all__ = ("format_size", "open_folder", "set_feedback")
