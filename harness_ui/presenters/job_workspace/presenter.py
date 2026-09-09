"""Composed presenter for progress and output-review views."""

from PySide6.QtCore import QObject, Signal
from modules.jobs import JobStore

from harness_ui.presenters.job_workspace.controls import JobControlPresenter
from harness_ui.presenters.job_workspace.header import JobHeaderPresenter
from harness_ui.presenters.job_workspace.outputs import JobOutputPresenter
from harness_ui.presenters.job_workspace.queue import JobQueuePresenter
from harness_ui.presenters.job_workspace.segments import JobSegmentPresenter
from harness_ui.presenters.job_workspace.state import JobWorkspaceSnapshot
from harness_ui.state import UiStateStore


class JobWorkspacePresenter(
    JobHeaderPresenter,
    JobQueuePresenter,
    JobOutputPresenter,
    JobSegmentPresenter,
    JobControlPresenter,
    QObject,
):
    """Own all rendering decisions for job progress and output review."""

    snapshotChanged = Signal(object)

    def __init__(
        self,
        *,
        parent,
        workspace,
        state: UiStateStore,
        service,
        worker,
        output_controller,
        runtime_summary,
        job_display_name,
    ):
        super().__init__(parent)
        self.header_view = workspace.header
        self.jobs_view = workspace.jobs
        self.queue_view = workspace.queue
        self.output_view = workspace.output
        self.media_player = workspace.media_player
        self.state = state
        self.service = service
        self.worker = worker
        self.output_controller = output_controller
        self._runtime_summary = runtime_summary
        self._job_display_name = job_display_name

    def _get(self, field):
        return self.state.get(field)

    def _set(self, field, value):
        self.state.set(field, value)

    def render_generation_snapshot(self, snapshot):
        """Render worker-owned state into the queue workspace."""

        self.queue_view.runtime_label.setText(snapshot.runtime_summary)
        self.update_controls()

    def reset_workspace(self, manifest=None):
        """Reset every job workspace section to a consistent blank state."""

        title = (
            manifest.get("name", "New TTS job")
            if manifest is not None
            else "New TTS job"
        )
        self.header_view.job_title.setText(title)
        self.header_view.job_title.setToolTip("")
        self.header_view.job_segment_count.setText("No segments")
        self._set("job_header_action_mode", "run")
        self.header_view.job_header_action.setText("Run job")
        self.header_view.job_progress.setValue(0)
        self.header_view.progress_text.setText("No active job")
        self.header_view.progress_panel.hide()
        self.header_view.completion_panel.hide()
        self._set("workspace_error_message", None)

        self.queue_view.queue_tree.clear()
        self.queue_view.queue_stack.setCurrentWidget(
            self.queue_view.queue_empty_state
        )
        self.output_view.output_list.clear()
        self.output_controller.release_media_source()
        self.show_output_state(None)
        self.output_view.segment_table.setRowCount(0)
        self.output_view.segment_editor.clear()
        self.show_segment_state(None)
        self._set("runtime_summary", "Runtime metrics appear after model load")
        self.render_generation_snapshot_from_state()

    def render_generation_snapshot_from_state(self):
        """Refresh the queue controls after a state-only workspace update."""

        self.queue_view.runtime_label.setText(
            str(self._get("runtime_summary"))
        )
        self.update_controls()

    def render_manifest(self, manifest):
        scripts = manifest.get("scripts", [])
        title = self._job_display_name(manifest)
        self.header_view.job_title.setText(title)
        self.header_view.job_title.setToolTip(
            f"{manifest['job_id']}\nCreated: {manifest.get('created_at', 'unknown')}"
        )
        status = str(manifest.get("status", "pending"))
        complete, total = JobStore.progress(manifest)
        percent = int((complete / total) * 100) if total else 0
        self.header_view.job_progress.setValue(percent)
        self.header_view.progress_text.setText(
            f"{complete}/{total} segments · {percent}%"
            if total
            else f"{sum(s.get('status') == 'complete' for s in scripts)}/{len(scripts)} scripts"
        )
        self.render_header_state(manifest, status, complete, total)
        error = manifest.get("error") or next(
            (script.get("error") for script in scripts if script.get("error")), None
        )
        self._set("workspace_error_message", str(error) if error else None)
        self._set(
            "runtime_summary",
            self._runtime_summary(manifest.get("runtime")),
        )
        self.render_generation_snapshot_from_state()
        self.render_queue(manifest)
        self.render_outputs(manifest)
        self.render_segments(manifest)
        self.update_controls()
        self.snapshotChanged.emit(
            JobWorkspaceSnapshot(
                job_id=str(manifest.get("job_id") or "") or None,
                status=status,
                completed_segments=complete,
                total_segments=total,
                output_count=len(self.service.output_paths(manifest)),
            )
        )
