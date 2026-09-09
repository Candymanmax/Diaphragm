"""Shared subprocess arguments for local model maintenance."""

from __future__ import annotations

from pathlib import Path
import sys


def _module_arguments(module_name, frozen_flag):
    if getattr(sys, "frozen", False):
        return (frozen_flag,)
    return ("-m", module_name)


def model_download_arguments(model_id, cache_root, operation="install"):
    """Build the command used by every GUI model-download action."""

    return (
        *_module_arguments("modules.model_download", "--model-download"),
        str(model_id).strip().lower(),
        "--cache-root",
        str(Path(cache_root).expanduser().resolve()),
        "--operation",
        str(operation).strip().lower(),
    )


def model_inventory_arguments(operation, model_id, cache_root):
    """Build the packaged or source command for inventory maintenance."""

    return (
        *_module_arguments("modules.model_inventory", "--model-inventory"),
        str(operation).strip().lower(),
        str(model_id).strip().lower(),
        "--cache-root",
        str(Path(cache_root).expanduser().resolve()),
    )


__all__ = ("model_download_arguments", "model_inventory_arguments")
