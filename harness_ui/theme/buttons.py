"""Shared button templates and dynamic widget-role helpers."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QPushButton, QToolButton

BUTTON_ROLES = ("neutral", "primary", "ghost", "danger")
BUTTON_HEIGHT = 30
BUTTON_ICON_SIZE = 16
ICON_BUTTON_SIZE = 30


def set_button_role(button, role="neutral"):
    if role not in BUTTON_ROLES:
        raise ValueError(f"Unknown button role: {role}")

    button.setProperty("buttonRole", role)

    for property_name in ("primary", "ghost", "danger"):
        button.setProperty(property_name, property_name == role)

    # Qt does not always re-evaluate stylesheet selectors when a dynamic
    # property changes after the widget has already been polished.
    style = button.style()
    if style is not None:
        style.unpolish(button)
        style.polish(button)
    button.update()

    return button


def standard_button(
    text="",
    *,
    role="neutral",
    parent=None,
    object_name=None,
    icon=None,
    icon_size=BUTTON_ICON_SIZE,
    accessible_name=None,
    tool_tip=None,
    variant=None,
):
    """Create a text button using the application's shared button template."""

    button = QPushButton(str(text), parent)
    if object_name:
        button.setObjectName(str(object_name))
    if isinstance(icon, QIcon):
        button.setIcon(icon)
        button.setIconSize(QSize(icon_size, icon_size))
    if accessible_name:
        button.setAccessibleName(str(accessible_name))
    if tool_tip:
        button.setToolTip(str(tool_tip))
    if variant:
        button.setProperty("buttonVariant", str(variant))
    button.setMinimumHeight(BUTTON_HEIGHT)
    return set_button_role(button, role)


def icon_button(
    icon=None,
    *,
    role="ghost",
    parent=None,
    object_name=None,
    icon_size=BUTTON_ICON_SIZE,
    size=ICON_BUTTON_SIZE,
    accessible_name=None,
    tool_tip=None,
    auto_raise=None,
    checkable=False,
):
    """Create an icon-only tool button using the shared button template."""

    button = QToolButton(parent)
    if object_name:
        button.setObjectName(str(object_name))
    if isinstance(icon, QIcon):
        button.setIcon(icon)
    button.setIconSize(QSize(icon_size, icon_size))
    button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
    button.setCheckable(bool(checkable))
    button.setAutoRaise(
        bool(role == "ghost") if auto_raise is None else bool(auto_raise)
    )
    if isinstance(size, QSize):
        button.setFixedSize(size)
    elif isinstance(size, (tuple, list)):
        button.setFixedSize(int(size[0]), int(size[1]))
    else:
        button.setFixedSize(int(size), int(size))
    if accessible_name:
        button.setAccessibleName(str(accessible_name))
    if tool_tip:
        button.setToolTip(str(tool_tip))
    button.setProperty("buttonVariant", "icon")
    return set_button_role(button, role)


__all__ = (
    "BUTTON_HEIGHT",
    "BUTTON_ICON_SIZE",
    "BUTTON_ROLES",
    "ICON_BUTTON_SIZE",
    "icon_button",
    "set_button_role",
    "standard_button",
)
