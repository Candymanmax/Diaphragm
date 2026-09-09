"""Persistent-job creation, preparation, execution, and control."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict

from modules.config import PipelineConfig
from modules.contracts import JobRequest
from modules.events import EventStreamWriter, emit_event
from modules.jobs import JobStoreError, utc_now


class JobExecutionService:
    """Coordinate job lifecycle around a persistent JobStore."""

    def __init__(
        self,
        *,
        paths,
        store,
        config_service,
        voice_library,
        ensure_folders,
        runner=None,
    ):
        self.paths = paths
        self.store = store
        self.config_service = config_service
        self.voice_library = voice_library
        self._ensure_folders = ensure_folders
        self.runner = runner

    def create(self, request, event_callback=None, config_override=None):
        if not isinstance(request, JobRequest):
            request = JobRequest(**dict(request))

        self._ensure_folders()
        config_path, defaults_path = self.config_service.config_paths(
            request.config_file,
            request.defaults_file,
        )
        if config_override is None:
            config = self.config_service.load(config_path, defaults_path)
        elif isinstance(config_override, PipelineConfig):
            config = config_override
        else:
            config = PipelineConfig(**dict(config_override))
        scripts = tuple(
            self.config_service.project_path(path)
            for path in request.scripts
        )

        if not scripts:
            raise JobStoreError("Select at least one script")

        voice = self.voice_library.resolve(
            request.voice_override or config.voice,
            config_path.parent,
        )
        manifest = self.store.create_job(
            scripts=scripts,
            settings=asdict(config),
            voice_file=voice,
            job_id=request.job_id,
            name=request.name,
        )
        emit_event(
            event_callback,
            "job.created",
            f"Created job {manifest['job_id']}",
            job_id=manifest["job_id"],
            payload={"manifest": manifest},
        )
        return manifest

    def create_draft(self, name, job_id=None):
        """Create only the durable metadata needed for an unsaved job."""

        self._ensure_folders()
        return self.store.create_draft(name, job_id=job_id)

    def delete_draft(self, job_id):
        return self.store.delete_draft(job_id)

    def prepare(
        self,
        job_id,
        *,
        retry_failed=False,
        restart=False,
        event_callback=None,
    ):
        manifest = self.store.prepare_for_resume(
            job_id,
            retry_failed=retry_failed,
            restart=restart,
        )
        emit_event(
            event_callback,
            "job.prepared",
            f"Prepared job {job_id}",
            job_id=job_id,
            payload={
                "retry_failed": retry_failed,
                "restart": restart,
                "manifest": manifest,
            },
        )
        return manifest

    def run_manifest(self, manifest, event_callback=None):
        runner = self.runner
        built_in_runner = runner is None

        if built_in_runner:
            from modules.pipeline import run_job as runner

        job_id = manifest["job_id"]

        if event_callback is None:
            if built_in_runner:
                return runner(
                    self.store,
                    manifest,
                    app_paths=self.paths,
                )

            return runner(self.store, manifest)

        stdout = EventStreamWriter(
            event_callback,
            level="info",
            job_id=job_id,
        )
        stderr = EventStreamWriter(
            event_callback,
            level="error",
            job_id=job_id,
        )

        with redirect_stdout(stdout), redirect_stderr(stderr):
            try:
                if built_in_runner:
                    return runner(
                        self.store,
                        manifest,
                        event_callback=event_callback,
                        app_paths=self.paths,
                    )

                return runner(
                    self.store,
                    manifest,
                    event_callback=event_callback,
                )
            finally:
                stdout.flush()
                stderr.flush()

    def run(
        self,
        job_id,
        *,
        retry_failed=False,
        restart=False,
        prepared=False,
        event_callback=None,
    ):
        manifest = (
            self.store.load(job_id)
            if prepared
            else self.prepare(
                job_id,
                retry_failed=retry_failed,
                restart=restart,
                event_callback=event_callback,
            )
        )
        return self.run_manifest(manifest, event_callback=event_callback)

    def list(self, *, include_archived=False):
        jobs = self.store.list_jobs()

        if include_archived:
            return jobs

        return [job for job in jobs if not job.get("archived", False)]

    def load(self, job_id, *, recover=False):
        manifest = self.store.load(job_id)
        return self.store.recover(manifest) if recover else manifest

    def set_archived(self, job_id, archived=True):
        manifest = self.store.load(job_id)

        if manifest.get("status") in {"running", "pausing", "cancelling"}:
            raise JobStoreError("A running job cannot be archived")

        manifest["archived"] = bool(archived)
        manifest["archived_at"] = utc_now() if archived else None
        self.store.save(manifest)
        return manifest

    def request_pause(self, job_id):
        self.store.request_pause(job_id)

    def request_cancel(self, job_id):
        self.store.request_cancel(job_id)


__all__ = ("JobExecutionService",)
