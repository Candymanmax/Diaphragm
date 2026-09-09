"""Typed generation-controller state."""

from dataclasses import dataclass


@dataclass(frozen=True)
class GenerationSnapshot:
    """Immutable status for generation controls and observers."""

    job_id: str | None
    worker_running: bool
    finished_handled: bool
    return_code: int | None
    runtime_summary: str = "Runtime metrics appear after model load"
    pause_requested: bool = False
    cancel_requested: bool = False
    error_message: str | None = None
