"""Compose the grouped Qt stylesheet and apply the active palette."""

import re

from harness_ui.theme.palette import *  # Internal stylesheet color vocabulary.
from harness_ui.theme.stylesheet.fragments import (
    CHROME,
    DIALOGS,
    CONTROLS,
    WORKSPACE,
    PREFERENCES,
)

APP_STYLESHEET = "\n".join((
    CHROME,
    DIALOGS,
    CONTROLS,
    WORKSPACE,
    PREFERENCES,
))

_LEGACY_COLOR_MAP = {
    "#16161d": BASE,
    "#1c1c22": MANTLE,
    "#1d1d1d": MANTLE,
    "#1e1e24": MANTLE,
    "#1f1f1f": MANTLE,
    "#202020": BASE,
    "#202a26": SURFACE_0,
    "#222229": MANTLE,
    "#232329": CRUST,
    "#241b21": MANTLE,
    "#242424": BASE,
    "#25171c": CRUST,
    "#25252d": SURFACE_0,
    "#272727": MANTLE,
    "#292929": SURFACE_0,
    "#292930": SURFACE_0,
    "#292931": SURFACE_0,
    "#2a2027": MANTLE,
    "#2b252c": MANTLE,
    "#2d2d2d": BASE,
    "#2d2d35": SURFACE_0,
    "#303030": SURFACE_0,
    "#303039": SURFACE_0,
    "#323232": SURFACE_0,
    "#332b34": SURFACE_0,
    "#343434": SURFACE_0,
    "#34343d": SURFACE_1,
    "#34343e": SURFACE_1,
    "#345044": GREEN,
    "#35242d": SURFACE_0,
    "#363636": SURFACE_1,
    "#383838": SURFACE_1,
    "#393942": SURFACE_1,
    "#3b3b44": SURFACE_1,
    "#3b3b45": SURFACE_1,
    "#3e303b": SURFACE_1,
    "#41414b": SURFACE_0,
    "#454545": SURFACE_1,
    "#454550": SURFACE_1,
    "#4b2d39": SURFACE_0,
    "#50505b": SURFACE_1,
    "#5b3444": SURFACE_1,
    "#5f5f69": OVERLAY_0,
    "#6f6f6f": OVERLAY_0,
    "#704052": SURFACE_2,
    "#745064": TEAL,
    "#83536a": TEAL,
    "#85dc9a": GREEN,
    "#8ec5ff": BLUE,
    "#92929e": OVERLAY_2,
    "#9a9a9a": OVERLAY_2,
    "#9b9ba7": OVERLAY_2,
    "#9fb2a7": SUBTEXT_0,
    "#a8627b": TEAL,
    "#a8a8b3": SUBTEXT_0,
    "#b7b7c2": SUBTEXT_1,
    "#e7a0b2": MAROON,
    "#eaf7ef": TEXT,
    "#ececec": TEXT,
    "#ececf0": TEXT,
    "#ededed": TEXT,
    "#ef5d8d": TEAL,
    "#f0f0f3": TEXT,
    "#f0f0f4": TEXT,
    "#f1c675": YELLOW,
    "#f1f1f4": TEXT,
    "#f2f2f2": TEXT,
    "#f2f2f5": TEXT,
    "#f4c486": TEAL,
    "#f4f4f7": TEXT,
    "#f5f5f7": TEXT,
    "#ff6b9d": TEAL,
    "#ff87ae": TEAL,
    "#ff8f86": RED,
    "#ff8fa1": TEAL,
    "#ff8fa9": TEAL,
    "#ff9e9d": TEAL,
    "#ffc0ce": FLAMINGO,
    "#ffd1de": TEAL,
    "#ffd59e": TEAL,
    "#ffe3bc": TEAL,
    "#ffe4eb": TEAL,
    "#ffffff": TEXT,
    "#999": OVERLAY_1,
    "#aaa": SUBTEXT_0,
    "#ddd": TEXT,
    "#eee": TEXT,
}

def _apply_palette(stylesheet):
    return re.sub(
        r"#[0-9A-Fa-f]{6}|#[0-9A-Fa-f]{3}(?![0-9A-Fa-f])",
        lambda match: _LEGACY_COLOR_MAP.get(
            match.group(0).lower(),
            match.group(0),
        ),
        stylesheet,
    )


_PALETTED_STYLESHEET = _apply_palette(APP_STYLESHEET)


def normalize_accent_name(value):
    name = str(value or "teal").strip().casefold()
    return name if name in ACCENT_COLORS else "teal"


def build_stylesheet(accent_name="teal"):
    accent = ACCENT_COLORS[normalize_accent_name(accent_name)]
    return _PALETTED_STYLESHEET.replace(TEAL, accent)


def active_accent_color():
    try:
        from PySide6.QtWidgets import QApplication

        application = QApplication.instance()
        value = application.property("ttsAccentColor") if application else None
    except (AttributeError, RuntimeError):
        value = None

    return str(value or TEAL)


APP_STYLESHEET = build_stylesheet()
