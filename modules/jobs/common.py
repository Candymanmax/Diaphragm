"""Shared job-store contracts, constants, and identifiers."""

from __future__ import annotations

from datetime import datetime, timezone
import re
import uuid


JOB_SCHEMA_VERSION = 1
JOB_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
RECOVERABLE_JOB_STATES = {"running", "pausing", "cancelling"}
RECOVERABLE_SCRIPT_STATES = {
    "running",
    "pausing",
    "paused",
    "cancelling",
    "cancelled",
    "interrupted",
}


class JobStoreError(RuntimeError):
    """Raised when a persistent job cannot be created or loaded safely."""


class JobControlRequested(RuntimeError):
    """Raised by the runner when a pause or cancel marker is observed."""

    def __init__(self, action):
        self.action = action
        super().__init__(f"Job {action} requested")


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_slug(value, fallback="script"):
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", str(value)).strip("-_")
    return slug[:60] or fallback


def new_job_id():
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{uuid.uuid4().hex[:8]}"


def validate_job_id(job_id):
    job_id = str(job_id).strip()

    if not job_id or not JOB_ID_PATTERN.fullmatch(job_id):
        raise JobStoreError(
            "Job IDs may contain only letters, numbers, underscores, "
            "and hyphens"
        )

    return job_id


__all__ = (
    "JOB_SCHEMA_VERSION",
    "RECOVERABLE_JOB_STATES",
    "RECOVERABLE_SCRIPT_STATES",
    "JobControlRequested",
    "JobStoreError",
    "new_job_id",
    "safe_slug",
    "utc_now",
    "validate_job_id",
)
