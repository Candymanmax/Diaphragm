from __future__ import annotations

import os
from pathlib import Path
import time


RETRYABLE_WINDOWS_ERRORS = {5, 32, 33}


class AtomicReplaceError(PermissionError):
    """A destination remained locked throughout atomic replacement retries."""


def replace_with_retry(
    source,
    destination,
    *,
    attempts=8,
    initial_delay=0.1,
):
    """Atomically replace a file, tolerating short Windows/OneDrive locks."""
    source = Path(source)
    destination = Path(destination)
    attempts = max(1, int(attempts))
    delay = max(0.0, float(initial_delay))

    for attempt in range(attempts):
        try:
            os.replace(source, destination)
            return
        except OSError as error:
            retryable = (
                isinstance(error, PermissionError)
                or getattr(error, "winerror", None)
                in RETRYABLE_WINDOWS_ERRORS
            )

            if not retryable:
                raise

            if attempt == attempts - 1:
                raise AtomicReplaceError(
                    f"Could not replace '{destination.name}' because the "
                    "existing output is open or temporarily locked. Stop "
                    "playback, close programs using the file, let OneDrive "
                    "finish syncing, then use Retry failed."
                ) from error

            time.sleep(delay)
            delay = min(1.0, max(0.05, delay * 2))
