from __future__ import annotations

from modules.events import emit_event
from modules.jobs import utc_now
from modules.merger import AudioMerger
from modules.normalizer import AudioNormalizer

from .chunks import ensure_script_chunks, generate_pending_chunks
from .control import check_control
from .publishing import atomic_copy, publish_chunk_archive, published_path


def process_job_script(
    store,
    manifest,
    script,
    config,
    voice,
    generator_provider,
    event_callback=None,
):
    del voice
    job_id = manifest["job_id"]
    print("\n==============================")
    print(f"PROCESSING: {script['name']}")
    print("==============================\n")

    script["status"] = "running"
    script["started_at"] = script.get("started_at") or utc_now()
    script["error"] = None
    store.save(manifest)
    emit_event(
        event_callback,
        "script.started",
        f"Processing {script['name']}",
        job_id=job_id,
        script_id=script["id"],
        payload={"status": "running"},
    )

    check_control(store, manifest, script, event_callback)
    print("[1/4] Preparing persistent text chunks")
    ensure_script_chunks(store, manifest, script, config)
    check_control(store, manifest, script, event_callback)

    failed_chunks = [
        chunk
        for chunk in script["chunks"]
        if chunk.get("status") == "failed"
    ]

    if failed_chunks:
        raise RuntimeError(
            f"{len(failed_chunks)} chunk(s) are failed; use Retry failed"
        )

    print("\n[2/4] Generating pending speech chunks")
    generate_pending_chunks(
        store,
        manifest,
        script,
        config,
        generator_provider,
        event_callback,
    )
    check_control(store, manifest, script, event_callback)

    incomplete_chunks = [
        chunk
        for chunk in script["chunks"]
        if chunk.get("status") != "complete"
    ]

    if incomplete_chunks:
        raise RuntimeError(
            f"{len(incomplete_chunks)} chunk(s) are not complete"
        )

    chunks_folder = store.resolve_artifact(
        job_id,
        script["chunks_directory"],
    )
    audio_folder = store.resolve_artifact(
        job_id,
        script["audio_directory"],
    )
    published = published_path(store, script["published_output"])

    if not config.merge_audio:
        print("\n[3/4] Merging disabled; publishing retained chunks")
        publish_chunk_archive(chunks_folder, audio_folder, published)
        print("\n[4/4] Normalising audio disabled")
        script["status"] = "complete"
        script["completed_at"] = utc_now()
        store.save(manifest)
        emit_event(
            event_callback,
            "script.completed",
            f"Completed {script['name']}",
            job_id=job_id,
            script_id=script["id"],
            payload={"status": "complete", "output": str(published)},
        )
        print(f"\nCompleted: {published}")
        return published

    output_file = store.resolve_artifact(job_id, script["output_path"])

    if not (output_file.is_file() and output_file.stat().st_size > 0):
        work_folder = store.resolve_artifact(
            job_id,
            script["work_directory"],
        )
        work_folder.mkdir(parents=True, exist_ok=True)
        merged_file = work_folder / f"merged.{config.output_format}"

        if not (merged_file.is_file() and merged_file.stat().st_size > 0):
            print("\n[3/4] Merging retained audio chunks")
            merger = AudioMerger(
                input_folder=audio_folder,
                chunks_folder=chunks_folder,
                output_file=merged_file,
                min_silence_ms=config.pause_min_ms,
                max_silence_ms=config.pause_max_ms,
                pause_mean_ms=config.pause_mean_ms,
                pause_std_ms=config.pause_std_ms,
                sample_rate=config.sample_rate,
                output_format=config.output_format,
                cleanup_inputs=False,
            )
            merger.merge()
        else:
            print("\n[3/4] Reusing completed merged audio")

        check_control(store, manifest, script, event_callback)

        if config.normalize_audio:
            print("\n[4/4] Normalising audio")
            normalizer = AudioNormalizer(
                input_file=merged_file,
                output_file=output_file,
                target_lufs=config.loudness_target_lufs,
            )
            normalizer.normalize()
        else:
            print("\n[4/4] Normalising audio disabled")
            atomic_copy(merged_file, output_file)
    else:
        print("\n[3/4] Reusing completed job output")
        print("\n[4/4] Normalisation already complete")

    check_control(store, manifest, script, event_callback)
    atomic_copy(output_file, published)
    script["status"] = "complete"
    script["completed_at"] = utc_now()
    script["error"] = None
    store.save(manifest)
    emit_event(
        event_callback,
        "script.completed",
        f"Completed {script['name']}",
        job_id=job_id,
        script_id=script["id"],
        payload={"status": "complete", "output": str(published)},
    )
    print(f"\nCompleted: {published}")
    return published
