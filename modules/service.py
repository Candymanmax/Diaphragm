"""Stable facade composing Diaphragm's backend services."""

from __future__ import annotations

from modules.app_settings import AppPaths
from modules.config_service import PipelineConfigService
from modules.contracts import JobRequest
from modules.job_execution import JobExecutionService
from modules.jobs import JobStore
from modules.output_catalog import OutputCatalog
from modules.segment_service import SegmentService
from modules.voice_library import VoiceLibrary


class TTSHarnessService:
    """Reusable facade shared by the GUI and generation worker."""

    def __init__(
        self,
        app_paths,
        *,
        runner=None,
    ):
        self.paths = (
            app_paths
            if isinstance(app_paths, AppPaths)
            else AppPaths.from_dict(app_paths)
        )
        self.project_root = self.paths.library_root
        self.install_root = self.paths.install_root
        self.model_cache_root = self.paths.model_cache_root
        self.config_service = PipelineConfigService(self.paths)
        self.store = JobStore(self.paths.jobs_root)
        self.voice_library = VoiceLibrary(self.paths)
        self.segment_service = SegmentService(self.store)
        self.output_catalog = OutputCatalog(self.paths)
        self._runner = runner
        self.job_execution = JobExecutionService(
            paths=self.paths,
            store=self.store,
            config_service=self.config_service,
            voice_library=self.voice_library,
            ensure_folders=self.ensure_project_folders,
            runner=runner,
        )

    def _project_path(self, value):
        return self.config_service.project_path(value)

    def ensure_project_folders(self):
        self.paths.ensure_writable_folders()
        self.paths.jobs_root.mkdir(parents=True, exist_ok=True)

    def config_paths(
        self,
        config_file="config.yaml",
        defaults_file="config.default.yaml",
    ):
        return self.config_service.config_paths(config_file, defaults_file)

    def load_config(
        self,
        config_file="config.yaml",
        defaults_file="config.default.yaml",
    ):
        return self.config_service.load(config_file, defaults_file)

    def save_config(
        self,
        values,
        config_file="config.yaml",
        defaults_file="config.default.yaml",
    ):
        return self.config_service.save(
            values,
            config_file,
            defaults_file,
        )

    def resolve_voice(self, value, config_folder=None):
        return self.voice_library.resolve(value, config_folder)

    def create_job(self, request, event_callback=None, config_override=None):
        return self.job_execution.create(
            request,
            event_callback,
            config_override=config_override,
        )

    def create_draft(self, name, job_id=None):
        return self.job_execution.create_draft(name, job_id=job_id)

    def delete_draft(self, job_id):
        return self.job_execution.delete_draft(job_id)

    def prepare_job(
        self,
        job_id,
        *,
        retry_failed=False,
        restart=False,
        event_callback=None,
    ):
        return self.job_execution.prepare(
            job_id,
            retry_failed=retry_failed,
            restart=restart,
            event_callback=event_callback,
        )

    def run_manifest(self, manifest, event_callback=None):
        self.job_execution.runner = self._runner
        return self.job_execution.run_manifest(manifest, event_callback)

    def run_job(
        self,
        job_id,
        *,
        retry_failed=False,
        restart=False,
        prepared=False,
        event_callback=None,
    ):
        self.job_execution.runner = self._runner
        return self.job_execution.run(
            job_id,
            retry_failed=retry_failed,
            restart=restart,
            prepared=prepared,
            event_callback=event_callback,
        )

    def list_jobs(self, *, include_archived=False):
        return self.job_execution.list(include_archived=include_archived)

    def load_job(self, job_id, *, recover=False):
        return self.job_execution.load(job_id, recover=recover)

    def set_archived(self, job_id, archived=True):
        return self.job_execution.set_archived(job_id, archived)

    def request_pause(self, job_id):
        return self.job_execution.request_pause(job_id)

    def request_cancel(self, job_id):
        return self.job_execution.request_cancel(job_id)

    def reset_chunks(self, job_id, script_id, chunk_ids):
        return self.segment_service.reset(job_id, script_id, chunk_ids)

    def update_chunk_text(self, job_id, script_id, chunk_id, text):
        return self.segment_service.update_text(
            job_id,
            script_id,
            chunk_id,
            text,
        )

    def list_voices(self):
        return self.voice_library.list()

    def import_voice(self, source):
        return self.voice_library.import_file(source)

    def output_paths(self, manifest):
        return self.output_catalog.paths_for(manifest)


__all__ = ("JobRequest", "TTSHarnessService")
