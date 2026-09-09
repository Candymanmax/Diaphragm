from __future__ import annotations

from pathlib import Path

from modules.adapters.registry import MODEL_ADAPTER_NAMES, MODEL_DOWNLOAD_FILES

from .discovery import (
    file_identity,
    inspect_model_inventory,
    repository_root,
    snapshot_candidates,
)
from .records import load_records, write_records


def remaining_snapshot_identities(repository_root_path):
    identities = set()
    snapshots = Path(repository_root_path) / "snapshots"

    if not snapshots.is_dir():
        return identities

    for candidate in snapshots.rglob("*"):
        if candidate.is_file():
            identities.add(file_identity(candidate))

    return identities


def prune_orphan_blobs(repository_root_path):
    root = Path(repository_root_path)
    blobs = root / "blobs"

    if not blobs.is_dir():
        return

    referenced = remaining_snapshot_identities(root)

    for blob in blobs.rglob("*"):
        if blob.is_file() and file_identity(blob) not in referenced:
            blob.unlink()

    for directory in sorted(
        (path for path in blobs.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        try:
            directory.rmdir()
        except OSError:
            pass


def remove_model_inventory(model_id, hub_cache, progress_callback=None):
    model_id = str(model_id).strip().lower()
    inspect_model_inventory(model_id, hub_cache)
    repository, required_files = MODEL_DOWNLOAD_FILES[model_id]
    root = repository_root(model_id, hub_cache)
    other_required = set()

    for other_model_id in MODEL_ADAPTER_NAMES:
        if other_model_id == model_id:
            continue
        other_repository, other_files = MODEL_DOWNLOAD_FILES[other_model_id]

        if (
            other_repository == repository
            and inspect_model_inventory(other_model_id, hub_cache).installed
        ):
            other_required.update(other_files)

    removable = tuple(
        filename
        for filename in required_files
        if filename not in other_required
    )
    candidates = snapshot_candidates(model_id, hub_cache)
    total = max(1, len(candidates) * max(1, len(removable)))
    current = 0
    removed_bytes = 0
    removed_identities = set()

    for snapshot, _present, _modified in candidates:
        for filename in removable:
            path = snapshot / filename
            if path.is_file() or path.is_symlink():
                identity = file_identity(path)

                if identity not in removed_identities:
                    try:
                        removed_bytes += path.stat().st_size
                    except OSError:
                        pass
                    removed_identities.add(identity)

                path.unlink()
            current += 1

            if progress_callback is not None:
                progress_callback(current, total)

        if not any(path.is_file() for path in snapshot.rglob("*")):
            try:
                snapshot.rmdir()
            except OSError:
                pass

    prune_orphan_blobs(root)
    records = load_records(hub_cache)
    records["models"].pop(model_id, None)
    write_records(hub_cache, records)
    return removed_bytes
