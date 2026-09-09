from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


INVENTORY_SCHEMA_VERSION = 1
INVENTORY_FILE_NAME = ".diaphragm-model-inventory.json"


@dataclass(frozen=True)
class ModelInventory:
    model_id: str
    repository: str
    snapshot: Path | None
    required_files: tuple[str, ...]
    present_files: tuple[str, ...]
    local_bytes: int
    installed: bool
    recorded: bool
    verified_at: str | None = None

    @property
    def present_count(self):
        return len(self.present_files)

    @property
    def required_count(self):
        return len(self.required_files)

    @property
    def state(self):
        if self.installed and self.recorded:
            return "installed"
        if self.installed:
            return "unverified"
        if self.present_files:
            return "partial"
        return "missing"

    @property
    def message(self):
        if self.installed and self.recorded:
            return "All required model files are present and recorded."
        if self.installed:
            return (
                "All required model files are present. Verify them to "
                "record their integrity."
            )
        if self.present_files:
            return (
                f"{self.present_count}/{self.required_count} required "
                "model files are present. Repair the installation."
            )
        return "This model is not installed in the selected model cache."


@dataclass(frozen=True)
class VerificationReport:
    model_id: str
    valid: bool
    recorded: bool
    message: str
