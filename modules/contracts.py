"""Typed requests shared by service, GUI, worker, and CLI boundaries."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JobRequest:
    scripts: tuple[str, ...]
    config_file: str = "config.yaml"
    defaults_file: str = "config.default.yaml"
    voice_override: str | None = None
    job_id: str | None = None
    name: str | None = None


__all__ = ("JobRequest",)
