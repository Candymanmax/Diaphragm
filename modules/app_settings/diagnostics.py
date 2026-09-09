from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import uuid

from PySide6.QtCore import QObject, QSettings, Signal

class DiagnosticLogStore:
    """Local session logs with bounded retention and path redaction."""

    def __init__(self, paths, retention_days=14):
        self.paths = paths
        self.retention_days = int(retention_days)
        self.paths.logs_root.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.path = self.paths.logs_root / (
            f"session-{timestamp}-{os.getpid()}.log"
        )
        self.prune()

    def _redact(self, value):
        text = str(value)
        replacements = (
            (self.paths.library_root, "<library>"),
            (self.paths.data_root, "<app-data>"),
            (Path.home(), "~"),
        )

        for path, label in replacements:
            variants = {str(path), path.as_posix()}

            for value in variants:
                text = re.sub(
                    re.escape(value),
                    lambda _match, replacement=label: replacement,
                    text,
                    flags=re.IGNORECASE,
                )

        return text

    def write(self, level, message, timestamp=None):
        timestamp = timestamp or datetime.now(timezone.utc).isoformat(
            timespec="milliseconds"
        )
        line = f"{timestamp} [{str(level).upper()}] {self._redact(message)}\n"

        with self.path.open("a", encoding="utf-8", newline="\n") as output:
            output.write(line)

    def prune(self, retention_days=None):
        days = self.retention_days if retention_days is None else int(retention_days)

        if days == 0:
            return

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        for candidate in self.paths.logs_root.glob("*.log"):
            try:
                modified = datetime.fromtimestamp(
                    candidate.stat().st_mtime,
                    tz=timezone.utc,
                )

                if modified < cutoff:
                    candidate.unlink()
            except OSError:
                continue

    def clear(self):
        for candidate in self.paths.logs_root.glob("*.log"):
            try:
                candidate.unlink()
            except OSError:
                continue

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.path = self.paths.logs_root / (
            f"session-{timestamp}-{os.getpid()}.log"
        )
