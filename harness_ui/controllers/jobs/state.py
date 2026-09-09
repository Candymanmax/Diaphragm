"""Typed job-controller state and display helpers."""

from dataclasses import dataclass
from datetime import datetime, timezone


def relative_time(value, now=None):
    """Return the compact relative timestamp used by job cards."""

    if not value:
        return "Unknown time"
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return "Unknown time"
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    seconds = max(0, int((current - timestamp).total_seconds()))
    if seconds < 60:
        return "Just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    if seconds < 604800:
        return f"{seconds // 86400}d ago"
    return timestamp.astimezone().strftime("%d %b")


@dataclass(frozen=True)
class JobSnapshot:
    """Immutable list-selection state exposed to other UI components."""

    current_job_id: str | None
    title: str
    status: str
    temporary: bool
    showing_archived: bool
    visible_job_ids: tuple[str, ...]
