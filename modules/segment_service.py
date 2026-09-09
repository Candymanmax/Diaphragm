"""Retained-segment editing and regeneration preparation."""

from __future__ import annotations

import shutil

from modules.jobs import JobStoreError


class SegmentService:
    """Mutate retained chunk artifacts through the persistent JobStore."""

    def __init__(self, store):
        self.store = store

    def reset(self, job_id, script_id, chunk_ids):
        manifest = self.store.load(job_id)

        if manifest.get("status") in {"running", "pausing", "cancelling"}:
            raise JobStoreError("Wait for the active worker before regenerating")

        if not manifest.get("settings", {}).get(
            "retain_job_artifacts",
            False,
        ):
            raise JobStoreError(
                "This job cleaned its segment files after success. Enable "
                "'Keep segment files for review' before running a job to "
                "regenerate individual segments."
            )

        script = next(
            (
                entry
                for entry in manifest["scripts"]
                if entry.get("id") == script_id
            ),
            None,
        )

        if script is None:
            raise JobStoreError(f"Script not found in job: {script_id}")

        selected = set(chunk_ids)

        if not selected:
            raise JobStoreError("Select at least one segment to regenerate")

        known = {chunk.get("id") for chunk in script.get("chunks", [])}
        missing = selected - known

        if missing:
            raise JobStoreError(
                "Unknown segment(s): " + ", ".join(sorted(missing))
            )

        for chunk in script.get("chunks", []):
            if chunk.get("id") not in selected:
                continue

            text_path = self.store.resolve_artifact(
                job_id,
                chunk.get("text_path"),
            )

            if text_path is None or not text_path.is_file():
                raise JobStoreError(
                    f"Segment text is unavailable: {chunk.get('id')}"
                )

            audio_path = self.store.resolve_artifact(
                job_id,
                chunk.get("audio_path"),
            )

            if audio_path is not None and audio_path.is_file():
                audio_path.unlink()

            chunk["status"] = "pending"
            chunk["error"] = None
            chunk["started_at"] = None
            chunk["completed_at"] = None
            chunk["elapsed_seconds"] = None

        work = self.store.resolve_artifact(
            job_id,
            script.get("work_directory"),
        )

        if work is not None and work.is_dir():
            shutil.rmtree(work)

        output = self.store.resolve_artifact(
            job_id,
            script.get("output_path"),
        )

        if output is not None and output.is_file():
            output.unlink()

        script["status"] = "pending"
        script["error"] = None
        script["completed_at"] = None
        script["artifacts_cleaned_at"] = None
        manifest["status"] = "pending"
        manifest["error"] = None
        manifest["completed_at"] = None
        manifest["artifact_cleanup"] = {
            "status": "pending",
            "completed_at": None,
            "error": None,
        }
        self.store.clear_controls(job_id)
        self.store.save(manifest)
        return manifest

    def update_text(self, job_id, script_id, chunk_id, text):
        text = str(text).strip()

        if not text:
            raise JobStoreError("Segment text cannot be empty")

        manifest = self.store.load(job_id)
        script = next(
            (
                entry
                for entry in manifest["scripts"]
                if entry.get("id") == script_id
            ),
            None,
        )

        if script is None:
            raise JobStoreError(f"Script not found in job: {script_id}")

        chunk = next(
            (
                entry
                for entry in script.get("chunks", [])
                if entry.get("id") == chunk_id
            ),
            None,
        )

        if chunk is None:
            raise JobStoreError(f"Segment not found: {chunk_id}")

        text_path = self.store.resolve_artifact(job_id, chunk["text_path"])

        if text_path is None or not text_path.is_file():
            raise JobStoreError("The retained segment text is unavailable")

        self.store._atomic_write_text(text_path, text + "\n")
        return self.reset(job_id, script_id, (chunk_id,))


__all__ = ("SegmentService",)
