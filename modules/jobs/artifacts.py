"""Path containment and atomic artifact operations for job storage."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import uuid

from modules.jobs.common import JobStoreError, validate_job_id


def job_folder(root, job_id):
    return Path(root) / validate_job_id(job_id)


def resolve_artifact(root, job_id, relative_path):
    if relative_path is None:
        return None

    relative_path = Path(str(relative_path))

    if relative_path.is_absolute():
        raise JobStoreError("Job artifact paths must be relative")

    folder = job_folder(root, job_id).resolve()
    candidate = (folder / relative_path).resolve()

    try:
        candidate.relative_to(folder)
    except ValueError as error:
        raise JobStoreError(
            f"Job artifact escapes its job folder: {relative_path}"
        ) from error

    return candidate


def artifact_relative(root, job_id, path):
    folder = job_folder(root, job_id).resolve()
    path = Path(path).resolve()

    try:
        return path.relative_to(folder).as_posix()
    except ValueError as error:
        raise JobStoreError(f"Path is outside job {job_id}: {path}") from error


def atomic_write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"

    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as file:
            json.dump(value, file, indent=2, ensure_ascii=False)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())

        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_write_text(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"

    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as file:
            file.write(value)
            file.flush()
            os.fsync(file.fileno())

        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_copy(source, destination):
    source = Path(source)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.parent / (
        f".{destination.name}.{uuid.uuid4().hex}.tmp"
    )

    try:
        shutil.copy2(source, temporary)

        with temporary.open("r+b") as copied_file:
            os.fsync(copied_file.fileno())

        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


__all__ = (
    "artifact_relative",
    "atomic_copy",
    "atomic_write_json",
    "atomic_write_text",
    "job_folder",
    "resolve_artifact",
)
