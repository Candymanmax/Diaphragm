"""Typed output-review state."""

from dataclasses import dataclass
from pathlib import Path


def format_media_time(milliseconds):
    seconds = max(0, int(milliseconds // 1000))
    return f"{seconds // 60}:{seconds % 60:02d}"


def is_playing_state(state):
    """Recognize Qt playback states without importing Qt Multimedia eagerly."""

    name = getattr(state, "name", None)
    if name is not None:
        return str(name) == "PlayingState"
    return str(state).rsplit(".", 1)[-1] == "PlayingState"


@dataclass(frozen=True)
class OutputReviewSnapshot:
    """Immutable playback and segment-selection state."""

    selected_output: Path | None
    selected_segment: tuple[str, str] | None
    playing: bool
    position_ms: int
    duration_ms: int
    worker_running: bool
