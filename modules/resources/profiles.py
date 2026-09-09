from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import uuid


PROFILE_SCHEMA_VERSION = 1


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class RuntimeProfileStore:
    """Atomic local memory profiles keyed by model and hardware."""

    def __init__(self, path="models/runtime_profiles.json"):
        self.path = Path(path)

    @staticmethod
    def profile_id(model_id, device_name, memory_mb):
        identity = (
            f"{str(model_id).lower()}|{device_name or 'CPU'}|"
            f"{int(memory_mb or 0)}"
        )
        return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]

    def _read(self):
        if not self.path.is_file():
            return {
                "schema_version": PROFILE_SCHEMA_VERSION,
                "profiles": {},
            }

        try:
            with self.path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {
                "schema_version": PROFILE_SCHEMA_VERSION,
                "profiles": {},
            }

        if (
            not isinstance(data, dict)
            or data.get("schema_version") != PROFILE_SCHEMA_VERSION
            or not isinstance(data.get("profiles"), dict)
        ):
            return {
                "schema_version": PROFILE_SCHEMA_VERSION,
                "profiles": {},
            }

        return data

    def get(self, profile_id):
        profile = self._read()["profiles"].get(profile_id, {})
        return dict(profile) if isinstance(profile, dict) else {}

    def save_profile(self, profile_id, profile):
        data = self._read()
        data["profiles"][profile_id] = dict(profile)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.parent / (
            f".{self.path.name}.{uuid.uuid4().hex}.tmp"
        )

        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as file:
                json.dump(data, file, indent=2, ensure_ascii=False)
                file.write("\n")
                file.flush()
                os.fsync(file.fileno())

            os.replace(temporary, self.path)
        finally:
            if temporary.exists():
                temporary.unlink()
