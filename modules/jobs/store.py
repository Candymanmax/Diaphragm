"""Core manifest persistence and control-marker storage."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

from modules.jobs.artifacts import (
    artifact_relative,
    atomic_copy,
    atomic_write_json,
    atomic_write_text,
    job_folder,
    resolve_artifact,
)
from modules.jobs.common import (
    JOB_SCHEMA_VERSION,
    JobStoreError,
    new_job_id,
    utc_now,
    validate_job_id,
)
from modules.jobs.manifest_factory import create_job
from modules.jobs.recovery import JobRecoveryService, progress


class JobStore:
    """Durable manifest storage and control markers for local TTS jobs."""

    def __init__(self, root="jobs"):
        self.root = Path(root).expanduser().resolve()
        self.recovery = JobRecoveryService(self)

    @staticmethod
    def new_job_id():
        return new_job_id()

    @staticmethod
    def validate_job_id(job_id):
        return validate_job_id(job_id)

    def job_folder(self, job_id):
        return job_folder(self.root, job_id)

    def manifest_path(self, job_id):
        return self.job_folder(job_id) / "manifest.json"

    def resolve_artifact(self, job_id, relative_path):
        return resolve_artifact(self.root, job_id, relative_path)

    def artifact_relative(self, job_id, path):
        return artifact_relative(self.root, job_id, path)

    _atomic_write_json = staticmethod(atomic_write_json)
    _atomic_write_text = staticmethod(atomic_write_text)
    _atomic_copy = staticmethod(atomic_copy)

    def create_job(
        self,
        scripts,
        settings,
        voice_file,
        job_id=None,
        name=None,
    ):
        return create_job(
            self,
            scripts,
            settings,
            voice_file,
            job_id=job_id,
            name=name,
        )

    def create_draft(self, name, job_id=None):
        """Persist a lightweight draft without staging generation files."""

        name = str(name).strip()
        if not name:
            raise JobStoreError("Job name cannot be empty")

        job_id = self.validate_job_id(
            job_id or f"draft-{new_job_id()}"
        )
        self.root.mkdir(parents=True, exist_ok=True)
        folder = self.job_folder(job_id)

        if folder.exists():
            raise JobStoreError(f"Job already exists: {job_id}")

        created_at = utc_now()
        manifest = {
            "schema_version": JOB_SCHEMA_VERSION,
            "job_id": job_id,
            "name": name,
            "status": "draft",
            "created_at": created_at,
            "updated_at": created_at,
            "started_at": None,
            "completed_at": None,
            "error": None,
            "archived": False,
            "archived_at": None,
            "temporary": True,
            "settings": {},
            "voice": {},
            "scripts": [],
        }

        created_folder = False
        try:
            folder.mkdir(parents=True, exist_ok=False)
            created_folder = True
            self._atomic_write_json(folder / "manifest.json", manifest)
        except Exception:
            if created_folder and folder.exists():
                shutil.rmtree(folder)
            raise

        return manifest

    def delete_draft(self, job_id):
        """Discard one persisted draft and its lightweight manifest."""

        manifest = self.load(job_id)
        if not manifest.get("temporary", False):
            raise JobStoreError("Only draft jobs can be discarded")

        folder = self.job_folder(job_id)
        if folder.is_dir():
            shutil.rmtree(folder)
        elif folder.exists():
            raise JobStoreError(f"Draft folder is not a directory: {folder}")

        return manifest

    def load(self, job_id):
        job_id = self.validate_job_id(job_id)
        manifest_file = self.manifest_path(job_id)

        if not manifest_file.is_file():
            raise JobStoreError(f"Job not found: {job_id}")

        try:
            with manifest_file.open("r", encoding="utf-8") as file:
                manifest = json.load(file)
        except (OSError, json.JSONDecodeError) as error:
            raise JobStoreError(
                f"Could not read job manifest: {manifest_file}"
            ) from error

        if not isinstance(manifest, dict):
            raise JobStoreError("Job manifest must contain an object")

        if manifest.get("schema_version") != JOB_SCHEMA_VERSION:
            raise JobStoreError(
                f"Unsupported job manifest version: "
                f"{manifest.get('schema_version')}"
            )

        if manifest.get("job_id") != job_id:
            raise JobStoreError("Job manifest ID does not match its folder")

        if not isinstance(manifest.get("scripts"), list):
            raise JobStoreError("Job manifest is missing its scripts list")

        return manifest

    def save(self, manifest):
        job_id = self.validate_job_id(manifest.get("job_id", ""))
        manifest["updated_at"] = utc_now()
        self._atomic_write_json(self.manifest_path(job_id), manifest)

    def list_jobs(self):
        if not self.root.is_dir():
            return []

        jobs = []

        for folder in self.root.iterdir():
            if not folder.is_dir() or folder.name.startswith("."):
                continue

            try:
                jobs.append(self.load(folder.name))
            except JobStoreError:
                continue

        return sorted(
            jobs,
            key=lambda manifest: manifest.get("created_at", ""),
            reverse=True,
        )

    def request_pause(self, job_id):
        self.load(job_id)
        marker = self.job_folder(job_id) / "control.pause"
        self._atomic_write_text(marker, f"requested_at={utc_now()}\n")

    def request_cancel(self, job_id):
        manifest = self.load(job_id)
        marker = self.job_folder(job_id) / "control.cancel"
        self._atomic_write_text(marker, f"requested_at={utc_now()}\n")

        if manifest.get("status") not in {
            "running",
            "pausing",
            "cancelling",
        }:
            manifest["status"] = "cancelled"
            manifest["error"] = None

            for script in manifest["scripts"]:
                if script.get("status") != "complete":
                    script["status"] = "cancelled"

            self.save(manifest)
        elif manifest.get("status") != "cancelling":
            # Record the request in the manifest as well as the durable
            # marker so the UI can acknowledge cancellation immediately.
            # The worker will transition this to "cancelled" at its next
            # safe checkpoint.
            manifest["status"] = "cancelling"
            manifest["error"] = None
            self.save(manifest)

    def control_action(self, job_id):
        folder = self.job_folder(job_id)

        if (folder / "control.cancel").is_file():
            return "cancel"

        if (folder / "control.pause").is_file():
            return "pause"

        return None

    def clear_controls(self, job_id):
        folder = self.job_folder(job_id)

        for name in ("control.pause", "control.cancel"):
            marker = folder / name

            if marker.is_file():
                marker.unlink()

    @staticmethod
    def _artifact_is_complete(path):
        return JobRecoveryService.artifact_is_complete(path)

    def recover(self, manifest):
        return self.recovery.recover(manifest)

    def prepare_for_resume(
        self,
        job_id,
        retry_failed=False,
        restart=False,
    ):
        return self.recovery.prepare_for_resume(
            job_id,
            retry_failed=retry_failed,
            restart=restart,
        )

    def cleanup_completed_artifacts(self, manifest):
        return self.recovery.cleanup_completed_artifacts(manifest)

    def cleanup_completed_jobs(self):
        return self.recovery.cleanup_completed_jobs()

    def _restart(self, manifest):
        return self.recovery.restart(manifest)

    @staticmethod
    def progress(manifest):
        return progress(manifest)


__all__ = ("JobStore",)
