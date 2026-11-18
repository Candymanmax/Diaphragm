from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import uuid

from PySide6.QtCore import QObject, QSettings, Signal

from modules.app_settings.models import *
from modules.app_settings.repository import _atomic_copy, _atomic_write_json

def file_sha256(path):
    digest = hashlib.sha256()

    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def directory_size(path):
    path = Path(path)
    total = 0

    if not path.exists():
        return 0

    for candidate in path.rglob("*"):
        try:
            if candidate.is_file():
                total += candidate.stat().st_size
        except OSError:
            continue

    return total


def _nearest_existing_parent(path):
    candidate = Path(path).expanduser().resolve()

    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent

    return candidate


def _is_nested(first, second):
    first = Path(first).resolve()
    second = Path(second).resolve()

    try:
        first.relative_to(second)
        return True
    except ValueError:
        return False


def _files_identical(first, second):
    first = Path(first)
    second = Path(second)
    return (
        first.is_file()
        and second.is_file()
        and first.stat().st_size == second.stat().st_size
        and file_sha256(first) == file_sha256(second)
    )


def _file_conflict_target(path, source):
    path = Path(path)
    index = 2

    while True:
        candidate = path.with_name(
            f"{path.stem}-imported-{index}{path.suffix}"
        )

        if not candidate.exists():
            return candidate, False

        if candidate.is_file() and _files_identical(candidate, source):
            return candidate, True

        index += 1


def _directories_identical(first, second):
    first = Path(first)
    second = Path(second)
    first_files = {
        path.relative_to(first).as_posix(): path
        for path in first.rglob("*")
        if path.is_file()
    }
    second_files = {
        path.relative_to(second).as_posix(): path
        for path in second.rglob("*")
        if path.is_file()
    }

    if first_files.keys() != second_files.keys():
        return False

    return all(
        _files_identical(path, second_files[relative])
        for relative, path in first_files.items()
    )


def _job_output_folders(source_id, target_id):
    return {
        Path("final") / origin / source_id: Path("final") / origin / target_id
        for origin in ("cli", "desktop")
    }


def _retarget_path(relative, folder_targets):
    for parent in relative.parents:
        if parent in folder_targets:
            return folder_targets[parent] / relative.relative_to(parent)
    return relative


def _remap_job_manifest(manifest, job_id):
    source_id = manifest.get("job_id")
    folder_targets = _job_output_folders(source_id, job_id) if source_id else {}
    manifest["job_id"] = job_id
    for script in manifest.get("scripts") or ():
        published = script.get("published_output")
        if published:
            relative = Path(published)
            target = _retarget_path(relative, folder_targets)
            if target != relative:
                script["published_output"] = target.as_posix()


def _job_outputs_compatible(source_job, target_job):
    for source_folder, target_folder in _job_output_folders(
        source_job.name, target_job.name
    ).items():
        source = source_job.parents[1] / source_folder
        target = target_job.parents[1] / target_folder
        if target.is_file() or any(
            not _files_identical(source / path.relative_to(target), path)
            for path in target.rglob("*")
            if path.is_file()
        ):
            return False
    return True


def _job_directories_equivalent(source, destination):
    source = Path(source)
    destination = Path(destination)
    source_files = {
        path.relative_to(source).as_posix(): path
        for path in source.rglob("*")
        if path.is_file()
    }
    destination_files = {
        path.relative_to(destination).as_posix(): path
        for path in destination.rglob("*")
        if path.is_file()
    }

    if source_files.keys() != destination_files.keys():
        return False

    for relative, source_file in source_files.items():
        destination_file = destination_files[relative]

        if relative != "manifest.json":
            if not _files_identical(source_file, destination_file):
                return False

            continue

        try:
            source_manifest = json.loads(
                source_file.read_text(encoding="utf-8")
            )
            destination_manifest = json.loads(
                destination_file.read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            return False

        _remap_job_manifest(source_manifest, "<job>")
        _remap_job_manifest(destination_manifest, "<job>")

        if source_manifest != destination_manifest:
            return False

    return True


def _job_conflict_target(source_job, target_job, reserved):
    target_job = Path(target_job)
    index = 2

    while True:
        candidate = target_job.with_name(
            f"{target_job.name}-imported-{index}"
        )

        if candidate not in reserved and _job_outputs_compatible(source_job, candidate):
            if not candidate.exists():
                return candidate, False

            if candidate.is_dir() and _job_directories_equivalent(source_job, candidate):
                return candidate, True

        index += 1


@dataclass(frozen=True)
class MigrationReport:
    source: Path
    destination: Path
    copied_files: int
    skipped_files: int
    copied_bytes: int
    staging_path: Path


def migrate_directory_verified(
    source,
    destination,
    *,
    include=None,
    conflict_mode="suffix",
    progress_callback=None,
    folder_targets=None,
):
    """Copy a directory through verified staging without touching source."""

    source = Path(source).expanduser().resolve()
    destination = Path(destination).expanduser().resolve()

    if not source.is_dir():
        raise PathMigrationError(f"Source folder does not exist: {source}")

    if source == destination:
        return MigrationReport(source, destination, 0, 0, 0, destination)

    if _is_nested(source, destination) or _is_nested(destination, source):
        raise PathMigrationError(
            "The new folder cannot be inside the current folder, or contain it."
        )

    include = tuple(include or (".",))
    folder_targets = folder_targets or {}

    if conflict_mode not in {"suffix", "error"}:
        raise ValueError(f"Unknown conflict mode: {conflict_mode}")

    files = []

    for relative_root in include:
        root = source if relative_root == "." else source / relative_root

        if not root.exists():
            continue

        files.extend(
            candidate
            for candidate in root.rglob("*")
            if candidate.is_file()
        )

    required_bytes = 0

    for candidate in files:
        target = destination / _retarget_path(candidate.relative_to(source), folder_targets)

        if not target.exists():
            required_bytes += candidate.stat().st_size
            continue

        if target.is_file() and _files_identical(target, candidate):
            continue

        if conflict_mode == "error":
            raise PathMigrationError(
                f"A different file already exists at {target}"
            )

        _target, identical_conflict = _file_conflict_target(
            target,
            candidate,
        )

        if not identical_conflict:
            required_bytes += candidate.stat().st_size

    free = shutil.disk_usage(_nearest_existing_parent(destination)).free

    if free < required_bytes:
        raise PathMigrationError(
            f"The destination needs at least {required_bytes / (1024 ** 3):.2f} "
            "GiB of free space."
        )

    migration_identity = f"{source}|{destination}|{include}|{conflict_mode}"
    if folder_targets:
        migration_identity += f"|{folder_targets}"
    migration_key = hashlib.sha256(migration_identity.encode("utf-8")).hexdigest()[:12]
    staging = destination.parent / f".diaphragm-import-{migration_key}.tmp"
    staging.mkdir(parents=True, exist_ok=True)
    journal_path = staging / "migration.json"
    journal_path.write_text(
        json.dumps(
            {
                "source": str(source),
                "destination": str(destination),
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    copied_files = 0
    skipped_files = 0
    copied_bytes = 0
    planned = []

    for index, candidate in enumerate(files, start=1):
        relative = candidate.relative_to(source)
        target = destination / _retarget_path(relative, folder_targets)

        if target.exists():
            if target.is_file() and _files_identical(target, candidate):
                skipped_files += 1

                if progress_callback:
                    progress_callback(index, len(files), copied_bytes)

                continue

            if conflict_mode == "error":
                raise PathMigrationError(
                    f"A different file already exists at {target}"
                )

            target, identical_conflict = _file_conflict_target(
                target,
                candidate,
            )

            if identical_conflict:
                skipped_files += 1

                if progress_callback:
                    progress_callback(index, len(files), copied_bytes)

                continue

        staged = staging / target.relative_to(destination)
        staged.parent.mkdir(parents=True, exist_ok=True)

        if not (
            staged.is_file()
            and staged.stat().st_size == candidate.stat().st_size
            and file_sha256(staged) == file_sha256(candidate)
        ):
            _atomic_copy(candidate, staged)

        if file_sha256(staged) != file_sha256(candidate):
            raise PathMigrationError(f"Verification failed for {relative}")

        planned.append((candidate, staged, target))
        copied_files += 1
        copied_bytes += candidate.stat().st_size

        if progress_callback:
            progress_callback(index, len(files), copied_bytes)

    destination.mkdir(parents=True, exist_ok=True)

    for _source_file, staged, target in planned:
        target.parent.mkdir(parents=True, exist_ok=True)

        if target.exists():
            raise PathMigrationError(
                f"The destination changed during migration: {target}"
            )

        os.replace(staged, target)

    if len(planned) != copied_files:
        raise PathMigrationError("Copied file count did not match the plan")

    for source_file, _staged, target in planned:
        if not _files_identical(source_file, target):
            raise PathMigrationError(
                f"Final verification failed for {target}"
            )

    if copied_files + skipped_files != len(files):
        raise PathMigrationError("Verified file count did not match the source")

    journal_path.unlink(missing_ok=True)
    shutil.rmtree(staging, ignore_errors=True)
    return MigrationReport(
        source=source,
        destination=destination,
        copied_files=copied_files,
        skipped_files=skipped_files,
        copied_bytes=copied_bytes,
        staging_path=staging,
    )


def migrate_library(source, destination, progress_callback=None):
    """Copy personal data, remapping colliding job IDs as whole jobs."""

    source = Path(source).expanduser().resolve()
    destination = Path(destination).expanduser().resolve()
    non_job_folders = tuple(
        name for name in LIBRARY_FOLDERS if name != "jobs"
    )
    all_files = [
        path
        for folder in non_job_folders
        for path in (source / folder).rglob("*")
        if path.is_file()
    ]
    source_jobs = source / "jobs"
    destination_jobs = destination / "jobs"
    job_plan = []
    output_targets = {}
    if source_jobs.is_dir():
        source_folders = [
            folder for folder in sorted(source_jobs.iterdir())
            if folder.is_dir() and not folder.name.startswith(".")
        ]
        reserved = {destination_jobs / folder.name for folder in source_folders}
        for source_job in source_folders:
            job_files = [path for path in source_job.rglob("*") if path.is_file()]
            all_files.extend(job_files)
            target_job = destination_jobs / source_job.name
            output_compatible = _job_outputs_compatible(source_job, target_job)
            already_imported = (
                output_compatible and target_job.is_dir()
                and _directories_identical(source_job, target_job)
            )
            if not already_imported and (target_job.exists() or not output_compatible):
                target_job, already_imported = _job_conflict_target(source_job, target_job, reserved)
                reserved.add(target_job)
                output_targets.update(_job_output_folders(source_job.name, target_job.name))
            job_plan.append((source_job, target_job, len(job_files), already_imported))
    total_files = len(all_files)
    completed_files = 0
    copied_bytes = 0

    def report_progress(current, _total, copied):
        if progress_callback:
            progress_callback(
                min(total_files, completed_files + current),
                total_files,
                copied_bytes + copied,
            )

    base_report = migrate_directory_verified(
        source,
        destination,
        include=non_job_folders,
        conflict_mode="suffix",
        progress_callback=report_progress,
        folder_targets=output_targets,
    )
    completed_files = sum(
        1
        for folder in non_job_folders
        for path in (source / folder).rglob("*")
        if path.is_file()
    )
    copied_files = base_report.copied_files
    skipped_files = base_report.skipped_files
    copied_bytes = base_report.copied_bytes
    for source_job, target_job, job_file_count, already_imported in job_plan:
        if already_imported:
            skipped_files += job_file_count
        else:
            job_report = migrate_directory_verified(
                source_job,
                target_job,
                include=(".",),
                conflict_mode="error",
                progress_callback=report_progress,
            )
            copied_files += job_report.copied_files
            skipped_files += job_report.skipped_files
            copied_bytes += job_report.copied_bytes

        manifest_path = target_job / "manifest.json"
        if target_job.name != source_job.name and manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as error:
                raise PathMigrationError(
                    f"Could not remap job manifest {manifest_path}"
                ) from error
            if manifest.get("job_id") != target_job.name:
                _remap_job_manifest(manifest, target_job.name)
                _atomic_write_json(manifest_path, manifest)

        completed_files += job_file_count
        if progress_callback:
            progress_callback(completed_files, total_files, copied_bytes)

    return MigrationReport(
        source=source,
        destination=destination,
        copied_files=copied_files,
        skipped_files=skipped_files,
        copied_bytes=copied_bytes,
        staging_path=base_report.staging_path,
    )


def migrate_model_cache(source, destination, progress_callback=None):
    return migrate_directory_verified(
        source,
        destination,
        include=(".",),
        conflict_mode="error",
        progress_callback=progress_callback,
    )
