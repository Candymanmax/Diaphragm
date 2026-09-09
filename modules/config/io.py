from __future__ import annotations

import os
from pathlib import Path
import shutil
import uuid

import yaml


def ensure_active_file(config_file, defaults_file):
    config_file = Path(config_file)
    defaults_file = Path(defaults_file)

    if config_file.exists():
        return config_file

    if not defaults_file.exists():
        raise FileNotFoundError(
            f"Default configuration file not found: {defaults_file}"
        )

    config_file.parent.mkdir(parents=True, exist_ok=True)
    temporary = config_file.parent / (
        f".{config_file.name}.{uuid.uuid4().hex}.tmp"
    )

    try:
        with (
            defaults_file.open("rb") as source,
            temporary.open("wb") as target,
        ):
            shutil.copyfileobj(source, target)
            target.flush()
            os.fsync(target.fileno())

        os.replace(temporary, config_file)
    finally:
        if temporary.exists():
            temporary.unlink()

    print(f"Created active configuration from defaults: {config_file}")
    return config_file


def read_mapping(config_file):
    config_file = Path(config_file)
    with config_file.open("r", encoding="utf-8") as file:
        values = yaml.safe_load(file) or {}

    if not isinstance(values, dict):
        raise ValueError("Configuration file must contain a YAML mapping")

    return values
