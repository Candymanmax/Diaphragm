"""Catppuccin Macchiato colors used throughout Diaphragm."""

# Catppuccin Macchiato palette supplied for the harness UI.
ROSEWATER = "#F4DBD6"
FLAMINGO = "#F0C6C6"
PINK = "#F5BDE6"
MAUVE = "#C6A0F6"
RED = "#ED8796"
MAROON = "#EE99A0"
PEACH = "#F5A97F"
YELLOW = "#EED49F"
GREEN = "#A6DA95"
TEAL = "#8BD5CA"
SKY = "#91D7E3"
SAPPHIRE = "#7DC4E4"
BLUE = "#8AADF4"
LAVENDER = "#B7BDF8"
TEXT = "#CAD3F5"
SUBTEXT_1 = "#B8C0E0"
SUBTEXT_0 = "#A5ADCB"
OVERLAY_2 = "#939AB7"
OVERLAY_1 = "#8087A2"
OVERLAY_0 = "#6E738D"
SURFACE_2 = "#5B6078"
SURFACE_1 = "#494D64"
SURFACE_0 = "#363A4F"
BASE = "#24273A"
MANTLE = "#1E2030"
CRUST = "#181926"

PALETTE = {
    "rosewater": ROSEWATER,
    "flamingo": FLAMINGO,
    "pink": PINK,
    "mauve": MAUVE,
    "red": RED,
    "maroon": MAROON,
    "peach": PEACH,
    "yellow": YELLOW,
    "green": GREEN,
    "teal": TEAL,
    "sky": SKY,
    "sapphire": SAPPHIRE,
    "blue": BLUE,
    "lavender": LAVENDER,
    "text": TEXT,
    "subtext_1": SUBTEXT_1,
    "subtext_0": SUBTEXT_0,
    "overlay_2": OVERLAY_2,
    "overlay_1": OVERLAY_1,
    "overlay_0": OVERLAY_0,
    "surface_2": SURFACE_2,
    "surface_1": SURFACE_1,
    "surface_0": SURFACE_0,
    "base": BASE,
    "mantle": MANTLE,
    "crust": CRUST,
}

ACCENT_COLORS = {
    name: PALETTE[name]
    for name in (
        "rosewater",
        "flamingo",
        "pink",
        "mauve",
        "red",
        "maroon",
        "peach",
        "yellow",
        "green",
        "teal",
        "sky",
        "sapphire",
        "blue",
        "lavender",
    )
}

ACCENT_START = TEAL
ACCENT_END = TEAL
MAIN_BACKGROUND = BASE
