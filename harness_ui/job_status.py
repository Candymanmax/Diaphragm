"""Shared visual metadata for persistent job states."""

from harness_ui.theme import (
    BLUE,
    GREEN,
    LAVENDER,
    RED,
    SUBTEXT_0,
    TEXT,
    YELLOW,
)


STATUS_COLORS = {
    "draft": SUBTEXT_0,
    "pending": SUBTEXT_0,
    "running": BLUE,
    "pausing": YELLOW,
    "paused": YELLOW,
    "cancelling": YELLOW,
    "cancelled": LAVENDER,
    "complete": GREEN,
    "failed": RED,
    "interrupted": YELLOW,
}


STATUS_LABELS = {
    "draft": "Draft",
    "pending": "Waiting",
    "running": "Running",
    "pausing": "Pausing",
    "paused": "Paused",
    "cancelling": "Cancelling",
    "cancelled": "Cancelled",
    "complete": "Complete",
    "failed": "Failed",
    "interrupted": "Interrupted",
}


def display_status(status):
    """Return a concise, user-facing label for a stored job status."""

    key = str(status or "pending").strip().casefold()
    return STATUS_LABELS.get(key, key.replace("_", " ").title() or "Unknown")


__all__ = ("STATUS_COLORS", "STATUS_LABELS", "display_status")
