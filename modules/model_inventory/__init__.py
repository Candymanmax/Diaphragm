"""Inspection, verification, and safe removal for cached TTS models."""

from .discovery import inspect_all_models, inspect_model_inventory
from .models import (
    INVENTORY_FILE_NAME,
    INVENTORY_SCHEMA_VERSION,
    ModelInventory,
    VerificationReport,
)
from .removal import remove_model_inventory
from .verification import record_model_inventory, verify_model_inventory

__all__ = [
    "INVENTORY_FILE_NAME",
    "INVENTORY_SCHEMA_VERSION",
    "ModelInventory",
    "VerificationReport",
    "inspect_all_models",
    "inspect_model_inventory",
    "record_model_inventory",
    "remove_model_inventory",
    "verify_model_inventory",
]
