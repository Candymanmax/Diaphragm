from __future__ import annotations

import json
import os
from pathlib import Path
import uuid

from .models import INVENTORY_FILE_NAME, INVENTORY_SCHEMA_VERSION


def inventory_path(hub_cache):
    return Path(hub_cache).expanduser().resolve() / INVENTORY_FILE_NAME


def load_records(hub_cache):
    path = inventory_path(hub_cache)

    if not path.is_file():
        return {"schema_version": INVENTORY_SCHEMA_VERSION, "models": {}}

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {"schema_version": INVENTORY_SCHEMA_VERSION, "models": {}}

    if not isinstance(value, dict) or not isinstance(
        value.get("models"), dict
    ):
        return {"schema_version": INVENTORY_SCHEMA_VERSION, "models": {}}

    value["schema_version"] = INVENTORY_SCHEMA_VERSION
    return value


def write_records(hub_cache, value):
    path = inventory_path(hub_cache)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")

    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as file:
            json.dump(value, file, indent=2, sort_keys=True)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())

        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()
