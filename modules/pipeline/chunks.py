from __future__ import annotations

import os
import shutil
import uuid

from modules.events import emit_event
from modules.jobs import JobStore, utc_now
from modules.splitter import ScriptSplitter

from .control import check_control


def chunk_entries_from_files(store, manifest, script, chunk_files):
    job_id = manifest["job_id"]
    audio_folder = store.resolve_artifact(
        job_id,
        script["audio_directory"],
    )
    audio_folder.mkdir(parents=True, exist_ok=True)
    entries = []

    for chunk_file in chunk_files:
        audio_file = audio_folder / f"{chunk_file.stem}.wav"
        complete = audio_file.is_file() and audio_file.stat().st_size > 0
        entries.append({
            "id": chunk_file.stem,
            "text_path": store.artifact_relative(job_id, chunk_file),
            "audio_path": store.artifact_relative(job_id, audio_file),
            "status": "complete" if complete else "pending",
            "attempts": 0,
            "error": None,
            "started_at": None,
            "completed_at": utc_now() if complete else None,
            "elapsed_seconds": None,
        })

    script["chunks"] = entries
    store.save(manifest)
    return entries


def ensure_script_chunks(store, manifest, script, config):
    job_id = manifest["job_id"]
    existing_entries = script.get("chunks", [])

    if existing_entries:
        existing_files = [
            store.resolve_artifact(job_id, chunk["text_path"])
            for chunk in existing_entries
        ]

        if all(path.is_file() for path in existing_files):
            return existing_entries

    chunks_folder = store.resolve_artifact(
        job_id,
        script["chunks_directory"],
    )
    discovered = (
        sorted(chunks_folder.glob("chunk*.txt"))
        if chunks_folder.is_dir()
        else []
    )

    if discovered and not existing_entries:
        return chunk_entries_from_files(
            store,
            manifest,
            script,
            discovered,
        )

    source_file = store.resolve_artifact(job_id, script["source_path"])
    staging = chunks_folder.parent / (
        f".{chunks_folder.name}.{uuid.uuid4().hex}.tmp"
    )

    try:
        splitter = ScriptSplitter(
            input_file=source_file,
            output_folder=staging,
            target_words=config.chunk_size,
            min_words=config.min_chunk_size,
        )
        splitter.split()
        generated = sorted(staging.glob("chunk*.txt"))

        if not generated:
            raise RuntimeError("Script splitting produced no chunks")

        if chunks_folder.exists():
            shutil.rmtree(chunks_folder)

        os.replace(staging, chunks_folder)
    finally:
        if staging.exists():
            shutil.rmtree(staging)

    return chunk_entries_from_files(
        store,
        manifest,
        script,
        sorted(chunks_folder.glob("chunk*.txt")),
    )


def generate_pending_chunks(
    store,
    manifest,
    script,
    config,
    generator_provider,
    event_callback=None,
):
    del config
    job_id = manifest["job_id"]
    chunks = script["chunks"]
    pending = [
        chunk
        for chunk in chunks
        if chunk.get("status") == "pending"
    ]

    if not pending:
        return

    chunks_folder = store.resolve_artifact(
        job_id,
        script["chunks_directory"],
    )
    audio_folder = store.resolve_artifact(
        job_id,
        script["audio_directory"],
    )
    audio_folder.mkdir(parents=True, exist_ok=True)
    chunk_files = [
        store.resolve_artifact(job_id, chunk["text_path"])
        for chunk in pending
    ]
    entries_by_path = {
        store.resolve_artifact(job_id, chunk["text_path"]).resolve(): chunk
        for chunk in chunks
    }

    # Check before loading the model so a request made while the worker is
    # preparing generation is honored without starting another operation.
    check_control(store, manifest, script, event_callback)
    generator = generator_provider(chunks_folder, audio_folder)
    # Model loading can take considerably longer than the UI refresh interval.
    # Re-check as soon as it returns so cancellation during that load is
    # acknowledged before any chunk is started.
    check_control(store, manifest, script, event_callback)

    def before_chunk(chunk_file, output_file):
        del output_file
        check_control(
            store,
            manifest,
            script,
            event_callback,
        )
        entry = entries_by_path[chunk_file.resolve()]
        entry["status"] = "running"
        entry["attempts"] = int(entry.get("attempts", 0)) + 1
        entry["started_at"] = utc_now()
        entry["completed_at"] = None
        entry["error"] = None
        store.save(manifest)
        emit_event(
            event_callback,
            "chunk.started",
            f"Generating {entry['id']}",
            job_id=job_id,
            script_id=script["id"],
            chunk_id=entry["id"],
            payload={"status": "running"},
        )

    def after_chunk(chunk_file, output_file, elapsed, skipped):
        del output_file
        entry = entries_by_path[chunk_file.resolve()]
        entry["status"] = "complete"
        entry["completed_at"] = utc_now()
        entry["elapsed_seconds"] = round(float(elapsed), 3)
        entry["error"] = None
        manifest["runtime"] = generator.runtime_report()
        store.save(manifest)
        emit_event(
            event_callback,
            "chunk.completed",
            f"Completed {entry['id']}",
            job_id=job_id,
            script_id=script["id"],
            chunk_id=entry["id"],
            payload={
                "elapsed_seconds": entry["elapsed_seconds"],
                "skipped": bool(skipped),
                "runtime": manifest["runtime"],
                "progress": JobStore.progress(manifest),
            },
        )

    def on_chunk_error(chunk_file, output_file, error):
        del output_file
        entry = entries_by_path[chunk_file.resolve()]
        entry["status"] = "failed"
        entry["error"] = f"{type(error).__name__}: {error}"
        entry["completed_at"] = None
        manifest["runtime"] = generator.runtime_report()
        store.save(manifest)
        emit_event(
            event_callback,
            "chunk.failed",
            entry["error"],
            job_id=job_id,
            script_id=script["id"],
            chunk_id=entry["id"],
            payload={
                "runtime": manifest["runtime"],
                "status": "failed",
            },
        )

    generator.run(
        chunk_files=chunk_files,
        output_folder=audio_folder,
        before_chunk=before_chunk,
        after_chunk=after_chunk,
        on_chunk_error=on_chunk_error,
    )
