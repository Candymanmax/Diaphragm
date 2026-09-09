"""Job recovery, resume preparation, restart, and artifact cleanup."""

from __future__ import annotations

import shutil

from modules.jobs.common import (
    RECOVERABLE_JOB_STATES,
    RECOVERABLE_SCRIPT_STATES,
    JobStoreError,
    utc_now,
)


class JobRecoveryService:
    """Apply recoverable state transitions through a JobStore."""

    def __init__(self, store):
        self.store = store

    @staticmethod
    def artifact_is_complete(path):
        return path is not None and path.is_file() and path.stat().st_size > 0

    def recover(self, manifest):
        changed = False
        job_id = manifest["job_id"]

        for script in manifest["scripts"]:
            for chunk in script.get("chunks", []):
                audio = self.store.resolve_artifact(
                    job_id,
                    chunk.get("audio_path"),
                )
                audio_complete = self.artifact_is_complete(audio)

                if chunk.get("status") == "running":
                    chunk["status"] = (
                        "complete" if audio_complete else "pending"
                    )
                    chunk["error"] = None
                    changed = True
                elif chunk.get("status") == "complete" and not audio_complete:
                    chunk["status"] = "pending"
                    chunk["completed_at"] = None
                    changed = True
                elif chunk.get("status") == "pending" and audio_complete:
                    chunk["status"] = "complete"
                    chunk["completed_at"] = (
                        chunk.get("completed_at") or utc_now()
                    )
                    changed = True

            if script.get("status") in RECOVERABLE_SCRIPT_STATES:
                script["status"] = "pending"
                changed = True

            output = self.store.resolve_artifact(
                job_id,
                script.get("output_path"),
            )

            if (
                script.get("status") == "complete"
                and manifest["settings"].get("merge_audio", True)
                and not self.artifact_is_complete(output)
            ):
                script["status"] = "pending"
                script["completed_at"] = None
                changed = True

        if manifest.get("status") in RECOVERABLE_JOB_STATES:
            manifest["status"] = "interrupted"
            manifest["error"] = (
                "The previous process ended before recording a terminal state."
            )
            changed = True

        if changed:
            self.store.save(manifest)

        return manifest

    def prepare_for_resume(
        self,
        job_id,
        retry_failed=False,
        restart=False,
    ):
        if retry_failed and restart:
            raise JobStoreError(
                "Retry failed and restart cannot be requested together"
            )

        manifest = self.store.load(job_id)

        if manifest.get("status") == "complete" and not restart:
            self.store.clear_controls(manifest["job_id"])

            if not manifest.get("settings", {}).get(
                "retain_job_artifacts",
                False,
            ):
                self.cleanup_completed_artifacts(manifest)

            return manifest

        manifest = self.recover(manifest)
        job_id = manifest["job_id"]
        self.store.clear_controls(job_id)

        if restart:
            self.restart(manifest)
        else:
            if manifest.get("status") in {
                "paused",
                "cancelled",
                "interrupted",
            }:
                manifest["status"] = "pending"
                manifest["error"] = None

            for script in manifest["scripts"]:
                if script.get("status") in RECOVERABLE_SCRIPT_STATES:
                    script["status"] = "pending"
                    script["error"] = None

                if retry_failed:
                    for chunk in script.get("chunks", []):
                        if chunk.get("status") == "failed":
                            audio = self.store.resolve_artifact(
                                job_id,
                                chunk.get("audio_path"),
                            )

                            if audio is not None and audio.is_file():
                                audio.unlink()

                            chunk["status"] = "pending"
                            chunk["error"] = None
                            chunk["completed_at"] = None

                    if script.get("status") == "failed":
                        script["status"] = "pending"
                        script["error"] = None
                        script["completed_at"] = None

            if retry_failed and manifest.get("status") == "failed":
                manifest["status"] = "pending"
                manifest["error"] = None

        self.store.save(manifest)
        return manifest

    def cleanup_completed_artifacts(self, manifest):
        if manifest.get("status") != "complete":
            raise JobStoreError(
                "Chunk artifacts can only be cleaned from a completed job"
            )

        job_id = manifest["job_id"]
        cleanup = manifest.setdefault("artifact_cleanup", {})

        if cleanup.get("status") == "complete":
            return manifest

        cleanup["status"] = "running"
        cleanup["completed_at"] = None
        cleanup["error"] = None
        self.store.save(manifest)

        try:
            for script in manifest["scripts"]:
                for directory_key in (
                    "chunks_directory",
                    "audio_directory",
                    "work_directory",
                ):
                    directory = self.store.resolve_artifact(
                        job_id,
                        script.get(directory_key),
                    )

                    if directory is None:
                        continue

                    if directory.is_dir():
                        shutil.rmtree(directory)
                    elif directory.exists():
                        directory.unlink()

                script["artifacts_cleaned_at"] = utc_now()
        except (JobStoreError, OSError) as error:
            cleanup["status"] = "failed"
            cleanup["error"] = f"{type(error).__name__}: {error}"
            self.store.save(manifest)
            raise

        cleanup["status"] = "complete"
        cleanup["completed_at"] = utc_now()
        cleanup["error"] = None
        self.store.save(manifest)
        return manifest

    def cleanup_completed_jobs(self):
        failures = []

        for manifest in self.store.list_jobs():
            if manifest.get("status") != "complete":
                continue

            if manifest.get("settings", {}).get(
                "retain_job_artifacts",
                False,
            ):
                continue

            cleanup = manifest.get("artifact_cleanup", {})

            if cleanup.get("status") == "complete":
                continue

            try:
                self.cleanup_completed_artifacts(manifest)
            except (JobStoreError, OSError) as error:
                failures.append((manifest["job_id"], str(error)))

        return failures

    def restart(self, manifest):
        job_id = manifest["job_id"]

        for script in manifest["scripts"]:
            for directory_key in ("audio_directory", "work_directory"):
                directory = self.store.resolve_artifact(
                    job_id,
                    script.get(directory_key),
                )

                if directory is not None and directory.is_dir():
                    shutil.rmtree(directory)

            output = self.store.resolve_artifact(
                job_id,
                script.get("output_path"),
            )

            if output is not None and output.is_file():
                output.unlink()

            for chunk in script.get("chunks", []):
                chunk["status"] = "pending"
                chunk["attempts"] = 0
                chunk["error"] = None
                chunk["started_at"] = None
                chunk["completed_at"] = None

            script["status"] = "pending"
            script["error"] = None
            script["started_at"] = None
            script["completed_at"] = None

        manifest["status"] = "pending"
        manifest["error"] = None
        manifest["started_at"] = None
        manifest["completed_at"] = None


def progress(manifest):
    chunks = [
        chunk
        for script in manifest.get("scripts", [])
        for chunk in script.get("chunks", [])
    ]
    complete = sum(chunk.get("status") == "complete" for chunk in chunks)
    return complete, len(chunks)


__all__ = ("JobRecoveryService", "progress")
