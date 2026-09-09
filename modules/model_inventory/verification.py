from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path

from .discovery import inspect_model_inventory
from .models import VerificationReport
from .records import load_records, write_records


def sha256(path):
    digest = hashlib.sha256()

    with Path(path).open("rb") as file:
        for block in iter(lambda: file.read(4 * 1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def record_model_inventory(model_id, hub_cache, progress_callback=None):
    inventory = inspect_model_inventory(model_id, hub_cache)

    if not inventory.installed or inventory.snapshot is None:
        raise RuntimeError(
            "All required files must be present before recording this model."
        )

    files = {}
    total = len(inventory.required_files)

    for index, filename in enumerate(inventory.required_files, start=1):
        path = inventory.snapshot / filename
        files[filename] = {
            "size": path.stat().st_size,
            "sha256": sha256(path),
        }

        if progress_callback is not None:
            progress_callback(index, total)

    records = load_records(hub_cache)
    records["models"][inventory.model_id] = {
        "repository": inventory.repository,
        "snapshot": inventory.snapshot.name,
        "verified_at": datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        ),
        "files": files,
    }
    write_records(hub_cache, records)
    return inspect_model_inventory(model_id, hub_cache)


def verify_model_inventory(model_id, hub_cache, progress_callback=None):
    inventory = inspect_model_inventory(model_id, hub_cache)

    if not inventory.installed or inventory.snapshot is None:
        return VerificationReport(
            inventory.model_id,
            False,
            False,
            "Required model files are missing. Use Repair to download them.",
        )

    records = load_records(hub_cache)
    record = records["models"].get(inventory.model_id)

    if not isinstance(record, dict) or (
        record.get("snapshot") != inventory.snapshot.name
    ):
        record_model_inventory(
            inventory.model_id,
            hub_cache,
            progress_callback=progress_callback,
        )
        return VerificationReport(
            inventory.model_id,
            True,
            True,
            "Model files were verified and recorded.",
        )

    expected_files = record.get("files")
    if not isinstance(expected_files, dict):
        expected_files = {}
    total = len(inventory.required_files)

    for index, filename in enumerate(inventory.required_files, start=1):
        path = inventory.snapshot / filename
        expected = expected_files.get(filename, {})
        actual_size = path.stat().st_size
        actual_hash = sha256(path)

        if progress_callback is not None:
            progress_callback(index, total)

        if (
            int(expected.get("size", -1)) != actual_size
            or expected.get("sha256") != actual_hash
        ):
            return VerificationReport(
                inventory.model_id,
                False,
                True,
                f"Verification failed for {filename}. Use Repair.",
            )

    record["verified_at"] = datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )
    records["models"][inventory.model_id] = record
    write_records(hub_cache, records)
    return VerificationReport(
        inventory.model_id,
        True,
        True,
        "All required model files passed verification.",
    )
