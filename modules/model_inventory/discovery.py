from __future__ import annotations

from pathlib import Path

from modules.adapters.registry import (
    MODEL_ADAPTER_NAMES,
    MODEL_DOWNLOAD_FILES,
    get_model_capabilities,
)

from .models import ModelInventory
from .records import load_records


def repository_folder(repository):
    return "models--" + str(repository).replace("/", "--")


def repository_root(model_id, hub_cache):
    repository, _required_files = MODEL_DOWNLOAD_FILES[str(model_id)]
    return Path(hub_cache).expanduser().resolve() / repository_folder(
        repository
    )


def snapshot_candidates(model_id, hub_cache):
    root = repository_root(model_id, hub_cache)
    snapshots = root / "snapshots"

    if not snapshots.is_dir():
        return ()

    _repository, required_files = MODEL_DOWNLOAD_FILES[str(model_id)]
    candidates = []

    for snapshot in snapshots.iterdir():
        if not snapshot.is_dir():
            continue

        present = tuple(
            filename
            for filename in required_files
            if (snapshot / filename).is_file()
        )
        try:
            modified = snapshot.stat().st_mtime_ns
        except OSError:
            modified = 0
        candidates.append((snapshot, present, modified))

    return tuple(candidates)


def best_snapshot(model_id, hub_cache):
    candidates = snapshot_candidates(model_id, hub_cache)

    if not candidates:
        return None, ()

    snapshot, present, _modified = max(
        candidates,
        key=lambda candidate: (
            len(candidate[1]),
            candidate[2],
            candidate[0].name,
        ),
    )
    return snapshot, present


def file_identity(path):
    path = Path(path)
    try:
        stat = path.stat()
        if stat.st_ino:
            return (stat.st_dev, stat.st_ino)
    except OSError:
        pass

    try:
        return str(path.resolve()).casefold()
    except OSError:
        return str(path.absolute()).casefold()


def selected_size(snapshot, filenames):
    if snapshot is None:
        return 0

    seen = set()
    total = 0

    for filename in filenames:
        path = Path(snapshot) / filename

        if not path.is_file():
            continue

        identity = file_identity(path)
        if identity in seen:
            continue
        seen.add(identity)

        try:
            total += path.stat().st_size
        except OSError:
            continue

    return total


def files_supplied_by_other_installed_models(model_id, hub_cache):
    repository, _required_files = MODEL_DOWNLOAD_FILES[str(model_id)]
    supplied = set()

    for other_model_id in MODEL_ADAPTER_NAMES:
        if other_model_id == model_id:
            continue

        other_repository, other_required = MODEL_DOWNLOAD_FILES[other_model_id]

        if other_repository != repository:
            continue

        _snapshot, other_present = best_snapshot(other_model_id, hub_cache)

        if len(other_present) == len(other_required):
            supplied.update(other_required)

    return supplied


def inspect_model_inventory(model_id, hub_cache):
    model_id = str(model_id).strip().lower()
    get_model_capabilities(model_id)
    repository, required_files = MODEL_DOWNLOAD_FILES[model_id]
    snapshot, present_files = best_snapshot(model_id, hub_cache)
    installed = len(present_files) == len(required_files)

    if not installed and present_files:
        supplied_elsewhere = files_supplied_by_other_installed_models(
            model_id,
            hub_cache,
        )
        present_files = tuple(
            filename
            for filename in present_files
            if filename not in supplied_elsewhere
        )

    records = load_records(hub_cache)
    record = records["models"].get(model_id)
    recorded = False
    verified_at = None

    if installed and isinstance(record, dict) and snapshot is not None:
        file_records = record.get("files")

        try:
            recorded = (
                record.get("repository") == repository
                and record.get("snapshot") == snapshot.name
                and isinstance(file_records, dict)
                and all(
                    isinstance(file_records.get(filename), dict)
                    and int(file_records[filename].get("size", -1))
                    == (snapshot / filename).stat().st_size
                    for filename in required_files
                )
            )
        except (OSError, TypeError, ValueError):
            recorded = False
        verified_at = (
            str(record.get("verified_at"))
            if recorded and record.get("verified_at")
            else None
        )

    return ModelInventory(
        model_id=model_id,
        repository=repository,
        snapshot=snapshot,
        required_files=tuple(required_files),
        present_files=tuple(present_files),
        local_bytes=selected_size(snapshot, present_files),
        installed=installed,
        recorded=recorded,
        verified_at=verified_at,
    )


def inspect_all_models(hub_cache):
    return {
        model_id: inspect_model_inventory(model_id, hub_cache)
        for model_id in MODEL_ADAPTER_NAMES
    }
