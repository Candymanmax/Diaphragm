"""Standard-library-only paths shared by settings and runtime setup."""

from __future__ import annotations

import os
from pathlib import Path
import sys


def local_app_data_root():
    configured = os.environ.get("LOCALAPPDATA")
    if configured:
        return Path(configured).expanduser().resolve()
    if sys.platform == "darwin":
        return (Path.home() / "Library" / "Application Support").resolve()
    return (Path.home() / ".local" / "share").resolve()
