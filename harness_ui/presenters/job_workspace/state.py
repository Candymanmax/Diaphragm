"""Typed summary published by the job workspace presenter."""

from dataclasses import dataclass


@dataclass(frozen=True)
class JobWorkspaceSnapshot:
    """Immutable summary of the job state currently shown to the user."""

    job_id: str | None
    status: str
    completed_segments: int
    total_segments: int
    output_count: int
