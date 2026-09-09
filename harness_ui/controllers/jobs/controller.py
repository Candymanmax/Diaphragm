"""Composed job-controller façade."""

from pathlib import Path
from dataclasses import asdict

from PySide6.QtCore import QObject, Qt, Signal

from harness_ui.controllers.jobs.lifecycle import JobLifecycleCommands
from harness_ui.controllers.jobs.menus import JobMenuCommands
from harness_ui.controllers.jobs.state import JobSnapshot
from harness_ui.controllers.jobs.view import JobViewCommands
from harness_ui.state import UiStateStore
from modules.config import PipelineConfig


class JobController(JobLifecycleCommands, JobMenuCommands, JobViewCommands, QObject):
    """Own job creation, selection, refresh, archive, and deletion."""

    snapshotChanged = Signal(object)
    tabRequested = Signal(int)

    def __init__(
        self,
        *,
        parent,
        workspace,
        state: UiStateStore,
        service,
        worker,
        settings_panel,
        diagnostics_controller,
        output_controller,
        presenter,
        settings_repository,
        prompt_job_name,
        move_to_trash,
        status_message,
    ):
        super().__init__(parent)
        self.parent_window = parent
        self.jobs_view = workspace.jobs
        self.state = state
        self.service = service
        self.worker = worker
        self.settings_panel = settings_panel
        self.diagnostics = diagnostics_controller
        self.output_controller = output_controller
        self.presenter = presenter
        self.settings_repository = settings_repository
        self._prompt_job_name = prompt_job_name
        self._move_to_trash = move_to_trash
        self._status_message = status_message
        self.generation_controller = None
        self._settings_context_key = None

    def bind_generation(self, controller):
        """Connect commands that require the generation controller."""

        self.generation_controller = controller

    def _get(self, field):
        return self.state.get(field)

    def _set(self, field, value):
        self.state.set(field, value)

    def sync_settings_context(self, manifest):
        """Show the selected job's snapshot, or the defaults for a blank view."""

        if manifest is None:
            try:
                config = self.service.load_config()
            except Exception as error:
                self.diagnostics.append(str(error), "error")
                return
        else:
            settings = dict(manifest.get("settings") or {})
            if not settings:
                try:
                    config = self.service.load_config()
                except Exception as error:
                    self.diagnostics.append(str(error), "error")
                    return
            else:
                # Jobs store a private copy of the voice under a stable path;
                # show its original library name in the inspector instead of
                # exposing the internal artifact path.
                voice = manifest.get("voice") or {}
                if voice.get("source_name"):
                    settings["voice"] = voice["source_name"]
                try:
                    config = PipelineConfig(**settings)
                except (TypeError, ValueError) as error:
                    self.diagnostics.append(str(error), "error")
                    return

        editable = bool(
            manifest is None
            or (
                manifest.get("temporary", False)
                and manifest.get("status") == "draft"
                and not self.worker.running
            )
        )
        context_key = (
            str((manifest or {}).get("job_id") or ""),
            str((manifest or {}).get("updated_at") or ""),
            editable,
            tuple(asdict(config).items()),
        )
        if context_key == self._settings_context_key:
            return

        self.settings_panel.set_config(config)
        self.settings_panel.set_job_scope(manifest, editable=editable)
        self._settings_context_key = context_key

    def settings_changed(self, config):
        """Persist edits made to the active draft without changing defaults."""

        if self.worker.running:
            return

        manifest = self._get("current_manifest") or {}
        if not manifest.get("temporary"):
            return

        if not isinstance(config, PipelineConfig):
            try:
                config = PipelineConfig(**dict(config))
            except (TypeError, ValueError) as error:
                self.diagnostics.append(str(error), "error")
                return

        updated = dict(manifest)
        updated["settings"] = asdict(config)
        try:
            self.service.store.save(updated)
        except (OSError, TypeError, ValueError) as error:
            self.diagnostics.append(
                f"Could not save draft settings: {error}",
                "error",
            )
            return

        temporary_jobs = dict(self._get("temporary_jobs"))
        temporary_jobs[updated["job_id"]] = updated
        self._set("temporary_jobs", temporary_jobs)
        self._set("current_manifest", updated)
        self._set("manifest_updated_at", updated.get("updated_at"))
        self._settings_context_key = None
        self._publish_snapshot()

    @staticmethod
    def display_name(manifest):
        raw_name = manifest.get("name")
        explicit_name = str(raw_name).strip() if raw_name else ""
        if explicit_name:
            return explicit_name
        names = [
            Path(script.get("name", "script")).stem
            for script in manifest.get("scripts", [])
        ]
        return names[0] if len(names) == 1 else f"{len(names)} scripts"

    def snapshot(self):
        manifest = self._get("current_manifest") or {}
        visible_ids = tuple(
            str(self.jobs_view.job_list.item(index).data(Qt.ItemDataRole.UserRole))
            for index in range(self.jobs_view.job_list.count())
        )
        job_id = self._get("current_job_id")
        return JobSnapshot(
            current_job_id=job_id,
            title=self.display_name(manifest) if manifest else "New TTS job",
            status=str(manifest.get("status", "draft")),
            temporary=self.is_temporary(job_id),
            showing_archived=bool(self._get("showing_archived_jobs")),
            visible_job_ids=visible_ids,
        )

    def _publish_snapshot(self):
        self.snapshotChanged.emit(self.snapshot())
