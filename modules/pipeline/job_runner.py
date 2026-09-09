from __future__ import annotations

import traceback

from modules.adapters.registry import format_model_capabilities
from modules.app_settings import AppPaths
from modules.config import PipelineConfig
from modules.events import emit_event
from modules.jobs import JobControlRequested, JobStoreError, utc_now

from .control import CANCELLED_EXIT_CODE, PAUSED_EXIT_CODE, check_control
from .generator_session import SharedGeneratorSession
from .script_runner import process_job_script


def run_job(store, manifest, event_callback=None, *, app_paths):
    if app_paths is None:
        raise ValueError("app_paths is required to run a job")

    app_paths = (
        app_paths
        if isinstance(app_paths, AppPaths)
        else AppPaths.from_dict(app_paths)
    )
    job_id = manifest["job_id"]

    if manifest.get("status") == "complete":
        if not manifest.get("settings", {}).get(
            "retain_job_artifacts",
            False,
        ):
            try:
                store.cleanup_completed_artifacts(manifest)
            except (JobStoreError, OSError) as error:
                print(
                    "Warning: completed-job cleanup will be retried: "
                    f"{error}"
                )

        print(f"Job {job_id} is already complete.")
        emit_event(
            event_callback,
            "job.completed",
            f"Job {job_id} is already complete",
            job_id=job_id,
            payload={"status": "complete"},
        )
        return 0

    config = PipelineConfig(**manifest["settings"])
    voice = store.resolve_artifact(job_id, manifest["voice"]["path"])

    if not voice.is_file():
        raise JobStoreError(f"Job voice reference is missing: {voice}")

    print("\n==============================")
    print("BULK TEXT TO SPEECH PIPELINE")
    print("==============================")
    print(f"Job ID: {job_id}")
    print(f"Scripts: {len(manifest['scripts'])}")
    print(
        f"Model: {config.model} | Language: {config.language} | "
        f"Sample rate: {config.sample_rate} Hz"
    )
    print("Capabilities: " + format_model_capabilities(config.model))

    manifest["status"] = "running"
    manifest["started_at"] = manifest.get("started_at") or utc_now()
    manifest["completed_at"] = None
    manifest["error"] = None
    store.save(manifest)
    emit_event(
        event_callback,
        "job.started",
        f"Started job {job_id}",
        job_id=job_id,
        payload={"status": "running"},
    )
    generator_session = SharedGeneratorSession(
        store=store,
        manifest=manifest,
        config=config,
        voice=voice,
        app_paths=app_paths,
        event_callback=event_callback,
    )

    try:
        for index, script in enumerate(manifest["scripts"], start=1):
            check_control(
                store,
                manifest,
                event_callback=event_callback,
            )
            print(f"\n\nSCRIPT {index}/{len(manifest['scripts'])}")

            try:
                if event_callback is None:
                    process_job_script(
                        store,
                        manifest,
                        script,
                        config,
                        voice,
                        generator_session,
                    )
                else:
                    process_job_script(
                        store,
                        manifest,
                        script,
                        config,
                        voice,
                        generator_session,
                        event_callback=event_callback,
                    )
            except JobControlRequested:
                raise
            except Exception as error:
                script["status"] = "failed"
                script["error"] = f"{type(error).__name__}: {error}"
                script["completed_at"] = None
                store.save(manifest)
                emit_event(
                    event_callback,
                    "script.failed",
                    script["error"],
                    job_id=job_id,
                    script_id=script["id"],
                    payload={"status": "failed"},
                )
                print(f"\nSCRIPT FAILED: {script['name']}: {error}")
                traceback.print_exc()

        failed_scripts = [
            script
            for script in manifest["scripts"]
            if script.get("status") != "complete"
        ]

        if failed_scripts:
            manifest["status"] = "failed"
            manifest["error"] = (
                f"{len(failed_scripts)} of {len(manifest['scripts'])} "
                "script(s) did not complete"
            )
            store.save(manifest)
            emit_event(
                event_callback,
                "job.failed",
                manifest["error"],
                job_id=job_id,
                payload={"status": "failed"},
            )
            print("\n==============================")
            print("JOB FINISHED WITH FAILURES")
            print("Use Retry failed after correcting the cause.")
            print("==============================")
            return 1

        manifest["status"] = "complete"
        manifest["completed_at"] = utc_now()
        manifest["error"] = None
        store.clear_controls(job_id)
        store.save(manifest)

        if config.retain_job_artifacts:
            manifest["artifact_cleanup"] = {
                "status": "retained",
                "completed_at": None,
                "error": None,
            }
            store.save(manifest)
            print("Retained segment files for review and regeneration.")
        else:
            try:
                store.cleanup_completed_artifacts(manifest)
                print("Removed completed text and audio chunk files.")
            except (JobStoreError, OSError) as error:
                print(
                    "Warning: final output is complete, but chunk cleanup "
                    f"will be retried later: {error}"
                )

        emit_event(
            event_callback,
            "job.completed",
            f"Completed job {job_id}",
            job_id=job_id,
            payload={"status": "complete"},
        )

        print("\n==============================")
        print("ALL SCRIPTS COMPLETE")
        print("==============================")
        return 0
    except JobControlRequested as request:
        return (
            PAUSED_EXIT_CODE
            if request.action == "pause"
            else CANCELLED_EXIT_CODE
        )
    except KeyboardInterrupt:
        manifest["status"] = "interrupted"
        manifest["error"] = "Interrupted from the console"
        store.save(manifest)
        emit_event(
            event_callback,
            "job.interrupted",
            manifest["error"],
            job_id=job_id,
            payload={"status": "interrupted"},
        )
        print("\nJob interrupted; use Resume to continue.")
        return 130
    finally:
        generator_session.close()
