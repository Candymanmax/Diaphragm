from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from harness_ui.theme import TEXT


LUCIDE_ICON_ROOT = Path(__file__).resolve().parent / "assets" / "icons"


@lru_cache(maxsize=128)
def _lucide_svg(name, color):
    if not name or Path(name).name != name:
        raise ValueError(f"Invalid Lucide icon name: {name!r}")

    path = LUCIDE_ICON_ROOT / f"{name}.svg"

    if not path.is_file():
        raise ValueError(f"Lucide icon is not bundled: {name}")

    resolved_color = QColor(color)

    if not resolved_color.isValid():
        raise ValueError(f"Invalid icon color: {color!r}")

    return path.read_text(encoding="utf-8").replace(
        "currentColor",
        resolved_color.name(QColor.NameFormat.HexRgb),
    )


def lucide_icon(name, *, color=TEXT, size=20):
    """Render a bundled Lucide SVG as a color-aware Qt icon."""
    size = int(size)

    if size <= 0:
        raise ValueError("Icon size must be positive")

    renderer = QSvgRenderer(QByteArray(_lucide_svg(name, color).encode()))

    if not renderer.isValid():
        raise ValueError(f"Lucide icon could not be rendered: {name}")

    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)
