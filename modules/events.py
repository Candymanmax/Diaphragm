from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import io
import re
import threading
from typing import Any, Callable


EVENT_SCHEMA_VERSION = 1
ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
TQDM_PROGRESS_RE = re.compile(
    r"^(?:[^:\r\n]{1,40}:\s*)?\d+%\|.*\|\s*\d+/\d+"
)


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


@dataclass(frozen=True)
class HarnessEvent:
    """One structured update emitted by the Diaphragm app."""

    kind: str
    message: str = ""
    job_id: str | None = None
    script_id: str | None = None
    chunk_id: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=utc_now)
    schema_version: int = EVENT_SCHEMA_VERSION

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict):
            raise ValueError("Harness event must be an object")

        if value.get("schema_version", EVENT_SCHEMA_VERSION) != (
            EVENT_SCHEMA_VERSION
        ):
            raise ValueError("Unsupported harness event schema")

        return cls(
            kind=str(value.get("kind", "unknown")),
            message=str(value.get("message", "")),
            job_id=value.get("job_id"),
            script_id=value.get("script_id"),
            chunk_id=value.get("chunk_id"),
            payload=dict(value.get("payload") or {}),
            timestamp=str(value.get("timestamp") or utc_now()),
        )


EventCallback = Callable[[HarnessEvent], None]


def emit_event(
    callback: EventCallback | None,
    kind: str,
    message: str = "",
    *,
    job_id: str | None = None,
    script_id: str | None = None,
    chunk_id: str | None = None,
    payload: dict[str, Any] | None = None,
):
    if callback is None:
        return None

    event = HarnessEvent(
        kind=kind,
        message=message,
        job_id=job_id,
        script_id=script_id,
        chunk_id=chunk_id,
        payload=dict(payload or {}),
    )
    callback(event)
    return event


class EventStreamWriter(io.TextIOBase):
    """Convert ordinary stdout/stderr lines into structured log events."""

    def __init__(self, callback, *, level="info", job_id=None):
        super().__init__()
        self.callback = callback
        self.level = str(level)
        self.job_id = job_id
        self._buffer = ""
        self._lock = threading.Lock()

    @property
    def encoding(self):
        return "utf-8"

    def writable(self):
        return True

    def write(self, value):
        value = str(value)

        with self._lock:
            self._buffer += value

            while "\n" in self._buffer or "\r" in self._buffer:
                newline = self._buffer.find("\n")
                carriage = self._buffer.find("\r")
                positions = [
                    position
                    for position in (newline, carriage)
                    if position >= 0
                ]
                boundary = min(positions)
                line, self._buffer = (
                    self._buffer[:boundary],
                    self._buffer[boundary + 1:],
                )
                self._emit_line(line)

        return len(value)

    @staticmethod
    def _clean_line(value):
        line = ANSI_ESCAPE_RE.sub("", str(value)).strip()

        # Chatterbox has nested tqdm bars for token sampling. The harness
        # already exposes script/chunk progress, and forwarding every redraw
        # creates thousands of unreadable GUI log entries.
        if not line or TQDM_PROGRESS_RE.match(line):
            return ""

        return line

    def _emit_line(self, value):
        line = self._clean_line(value)

        if line:
            emit_event(
                self.callback,
                "log",
                line,
                job_id=self.job_id,
                payload={"level": self.level},
            )

    def flush(self):
        with self._lock:
            self._emit_line(self._buffer)
            self._buffer = ""
