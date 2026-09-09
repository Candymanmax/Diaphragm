from __future__ import annotations

import os
from pathlib import Path
import shutil
import uuid

from modules.files import replace_with_retry
from modules.jobs import JobStoreError


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

        replace_with_retry(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def published_path(store, relative_path):
    relative_path = Path(str(relative_path))

    if relative_path.is_absolute():
        raise JobStoreError("Published output paths must be relative")

    final_root = (store.root.parent / "final").resolve()
    candidate = (store.root.parent / relative_path).resolve()

    try:
        candidate.relative_to(final_root)
    except ValueError as error:
        raise JobStoreError(
            f"Published output escapes the final folder: {relative_path}"
        ) from error

    return candidate


def publish_chunk_archive(chunks_folder, audio_folder, destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.parent / (
        f".{destination.name}.{uuid.uuid4().hex}.tmp"
    )
    backup = destination.parent / (
        f".{destination.name}.{uuid.uuid4().hex}.backup"
    )
    moved_existing = False

    try:
        (staging / "text").mkdir(parents=True)
        (staging / "audio").mkdir(parents=True)

        for chunk in sorted(Path(chunks_folder).glob("chunk*.txt")):
            atomic_copy(chunk, staging / "text" / chunk.name)

        for audio in sorted(Path(audio_folder).glob("chunk*.wav")):
            atomic_copy(audio, staging / "audio" / audio.name)

        if destination.exists():
            os.replace(destination, backup)
            moved_existing = True

        os.replace(staging, destination)

        if backup.is_dir():
            shutil.rmtree(backup)
        elif backup.exists():
            backup.unlink()
    except Exception:
        if moved_existing and backup.exists() and not destination.exists():
            os.replace(backup, destination)
        raise
    finally:
        if staging.is_dir():
            shutil.rmtree(staging)
        elif staging.exists():
            staging.unlink()
