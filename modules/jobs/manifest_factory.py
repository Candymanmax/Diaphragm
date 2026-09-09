"""Staged creation of immutable job inputs and initial manifests."""

from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path
import shutil
import uuid

from modules.jobs.common import (
    JOB_SCHEMA_VERSION,
    JobStoreError,
    safe_slug,
    utc_now,
)


def create_job(store, scripts, settings, voice_file, job_id=None, name=None):
    scripts = [Path(script).expanduser().resolve() for script in scripts]

    if not scripts:
        raise JobStoreError("A job must contain at least one script")

    for script in scripts:
        if not script.is_file() or script.suffix.lower() != ".txt":
            raise JobStoreError(f"Invalid script file: {script}")

    voice_file = Path(voice_file).expanduser().resolve()

    if not voice_file.is_file():
        raise JobStoreError(f"Voice reference not found: {voice_file}")

    job_id = store.validate_job_id(job_id or store.new_job_id())
    store.root.mkdir(parents=True, exist_ok=True)
    final_folder = store.job_folder(job_id)

    if final_folder.exists():
        raise JobStoreError(f"Job already exists: {job_id}")

    staging = store.root / f".{job_id}.{uuid.uuid4().hex}.tmp"
    created_at = utc_now()

    try:
        staging.mkdir(parents=True, exist_ok=False)
        voice_suffix = voice_file.suffix.lower() or ".wav"
        voice_relative = Path("voice") / f"reference{voice_suffix}"
        store._atomic_copy(voice_file, staging / voice_relative)
        output_format = str(settings.get("output_format", "wav"))
        output_format = output_format.lower().lstrip(".")
        script_entries = []
        used_output_names = set()

        for index, source in enumerate(scripts, start=1):
            script_id = (
                f"{index:03d}-{safe_slug(source.stem, f'script-{index}')}"
            )
            script_root = Path("scripts") / script_id
            source_relative = script_root / "source.txt"
            store._atomic_copy(source, staging / source_relative)
            output_stem = safe_slug(source.stem, f"script-{index}")
            candidate = output_stem
            suffix_number = 2

            while candidate.lower() in used_output_names:
                candidate = f"{output_stem}-{suffix_number}"
                suffix_number += 1

            used_output_names.add(candidate.lower())
            output_relative = (
                script_root / "output" / f"{candidate}.{output_format}"
            )

            if settings.get("merge_audio", True):
                published_output = f"final/{candidate}.{output_format}"
            else:
                published_output = f"final/{candidate}_chunks"

            script_entries.append({
                "id": script_id,
                "name": source.name,
                "source_path": source_relative.as_posix(),
                "chunks_directory": (script_root / "chunks").as_posix(),
                "audio_directory": (script_root / "audio").as_posix(),
                "work_directory": (script_root / "work").as_posix(),
                "output_path": output_relative.as_posix(),
                "published_output": published_output,
                "status": "pending",
                "error": None,
                "started_at": None,
                "completed_at": None,
                "artifacts_cleaned_at": None,
                "chunks": [],
            })

        resolved_settings = deepcopy(dict(settings))
        resolved_settings["voice"] = voice_relative.as_posix()
        manifest = {
            "schema_version": JOB_SCHEMA_VERSION,
            "job_id": job_id,
            "name": str(name).strip() if name else None,
            "status": "pending",
            "created_at": created_at,
            "updated_at": created_at,
            "started_at": None,
            "completed_at": None,
            "error": None,
            "archived": False,
            "archived_at": None,
            "artifact_cleanup": {
                "status": "pending",
                "completed_at": None,
                "error": None,
            },
            "settings": resolved_settings,
            "voice": {
                "path": voice_relative.as_posix(),
                "source_name": voice_file.name,
            },
            "scripts": script_entries,
        }
        store._atomic_write_json(staging / "manifest.json", manifest)
        os.replace(staging, final_folder)
        return manifest
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise


__all__ = ("create_job",)
