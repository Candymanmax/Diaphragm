"""Workspace-level feedback rendering."""

from __future__ import annotations


class WorkspaceFeedbackViewAdapter:
    """Render shared header feedback from application state transitions."""

    def __init__(self, header):
        self.header = header

    def render(self, _previous, message):
        """Show or clear the shared error banner idempotently."""

        message = str(message) if message else ""
        if message:
            self.header.error_banner.setText(message)
            self.header.error_banner.show()
        else:
            self.header.error_banner.hide()


__all__ = ("WorkspaceFeedbackViewAdapter",)
