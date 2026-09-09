"""Application font selection with a predictable platform fallback."""

from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtGui import QFont, QFontDatabase


_BUNDLED_INTER_FONT = (
    Path("harness_ui") / "assets" / "fonts" / "Inter[opsz,wght].ttf"
)
_font_load_attempted = False
_inter_font_id = -1


def bundled_inter_font_path():
    """Return the Inter asset path for source and bundled application runs."""
    bundle_root = Path(
        getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2])
    )
    return bundle_root / _BUNDLED_INTER_FONT


def load_bundled_ui_font():
    """Register the bundled Inter font before any widgets are created."""
    global _font_load_attempted, _inter_font_id

    if _font_load_attempted:
        return _inter_font_id >= 0

    _font_load_attempted = True
    path = bundled_inter_font_path()

    if not path.is_file():
        return False

    _inter_font_id = QFontDatabase.addApplicationFont(str(path))
    return _inter_font_id >= 0


def preferred_ui_font():
    """Return Inter when available, followed by the platform UI font."""
    system_font = QFontDatabase.systemFont(
        QFontDatabase.SystemFont.GeneralFont
    )
    font = QFont(system_font)
    fallback_family = system_font.family()
    families = ["Inter"]

    if fallback_family and fallback_family.casefold() != "inter":
        families.append(fallback_family)

    font.setFamilies(families)
    # Inter's small UI glyphs render more evenly without platform hinting,
    # especially on Windows at fractional scaling factors.
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return font


__all__ = (
    "bundled_inter_font_path",
    "load_bundled_ui_font",
    "preferred_ui_font",
)
