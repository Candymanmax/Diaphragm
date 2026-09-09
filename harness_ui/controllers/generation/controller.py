"""Composed generation controller façade."""

from PySide6.QtCore import QObject, Signal

from harness_ui.controllers.generation.commands import GenerationCommands
from harness_ui.controllers.generation.state import GenerationSnapshot
from harness_ui.controllers.generation.worker import GenerationWorkerCommands
from harness_ui.state import UiStateStore


class GenerationController(GenerationCommands, GenerationWorkerCommands, QObject):
    """Create jobs and supervise the isolated generation worker."""

    snapshotChanged = Signal(object)
    settingsRequested = Signal()
    logsRequested = Signal()
    tabRequested = Signal(int)

    def __init__(
        self,
        *,
        parent,
        state: UiStateStore,
        service,
        worker,
        script_controller,
        output_controller,
        diagnostics_controller,
        settings_panel,
        paths,
        settings_repository,
        ensure_job,
        job_display_name,
        refresh_jobs,
        refresh_current_job,
        status_message,
    ):
        super().__init__(parent)
        self.parent_window = parent
        self.state = state
        self.service = service
        self.worker = worker
        self.script_controller = script_controller
        self.output_controller = output_controller
        self.diagnostics = diagnostics_controller
        self.settings_panel = settings_panel
        self.paths = paths
        self.settings_repository = settings_repository
        self._ensure_job = ensure_job
        self._job_display_name = job_display_name
        self._refresh_jobs = refresh_jobs
        self._refresh_current_job = refresh_current_job
        self._status_message = status_message

    def _get(self, field):
        return self.state.get(field)

    def _set(self, field, value):
        self.state.set(field, value)

    def snapshot(self):
        return GenerationSnapshot(
            job_id=self._get("current_job_id"),
            worker_running=bool(self.worker.running),
            finished_handled=bool(self._get("worker_finished_handled")),
            return_code=self._get("worker_return_code"),
            runtime_summary=str(self._get("runtime_summary")),
            pause_requested=bool(self._get("pause_requested")),
            cancel_requested=bool(self._get("cancel_requested")),
            error_message=self._get("workspace_error_message"),
        )

    def _publish_snapshot(self):
        self.snapshotChanged.emit(self.snapshot())
