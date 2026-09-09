"""Shared ownership boundary for workspace sections."""

from __future__ import annotations

from harness_ui.state import UiStateStore
from harness_ui.theme import CONTROL_SPACING


class StatefulSection:
    """Own a focused group of widgets backed by shared UI state."""

    def __init__(self, state: UiStateStore):
        self.state = state


__all__ = ("CONTROL_SPACING", "StatefulSection")
