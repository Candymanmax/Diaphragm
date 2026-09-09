"""Enablement and visibility rules for workspace controls."""


class JobControlPresenter:
    """Apply current worker/job state to actionable controls."""

    def render_script_snapshot(self, snapshot):
        """Refresh run enablement when the checked-script count changes."""

        self._selected_script_count = int(snapshot.selected_documents)
        self.update_controls()

    def update_controls(self):
        running = self.worker.running
        manifest = self._get("current_manifest") or {}
        status = manifest.get("status")
        has_job = bool(self._get("current_job_id"))
        worker_has_job = running and has_job
        has_selected_scripts = bool(
            getattr(self, "_selected_script_count", 0)
        )
        current_segment = self._get("current_segment")
        self.jobs_view.new_job_button.setEnabled(not running)
        self.jobs_view.job_list.setEnabled(not running)
        self.output_view.output_list.setEnabled(not running)
        self.output_view.open_output_button.setEnabled(
            not running and self.output_view.output_list.currentItem() is not None
        )
        self.output_view.play_button.setEnabled(
            not running and not self.media_player.source().isEmpty()
        )
        self.output_view.play_segment_button.setEnabled(
            not running and self.output_controller.segment_audio_path() is not None
        )
        self.output_view.save_segment_button.setEnabled(
            not running
            and current_segment is not None
            and self.output_view.segment_editor.isEnabled()
        )
        self.queue_view.pause_button.setEnabled(
            worker_has_job
            and status == "running"
            and not self._get("pause_requested")
        )
        self.queue_view.cancel_button.setEnabled(
            worker_has_job and not self._get("cancel_requested")
        )
        self.queue_view.cancel_button.setText(
            "Cancelling…" if self._get("cancel_requested") else "Cancel"
        )
        self.queue_view.resume_button.setEnabled(
            has_job and not running and status in {"pending", "paused", "cancelled", "interrupted"}
        )
        self.queue_view.retry_button.setEnabled(has_job and not running and status == "failed")
        self.queue_view.restart_button.setEnabled(
            has_job and not running and status in {"complete", "failed"}
        )
        queue_has_content = (
            has_job
            and self.queue_view.queue_stack.currentWidget() is self.queue_view.queue_tree
        )
        self.queue_view.pause_button.setVisible(
            queue_has_content and status == "running"
        )
        self.queue_view.cancel_button.setVisible(
            queue_has_content and worker_has_job
        )
        self.queue_view.resume_button.setVisible(
            queue_has_content
            and status in {"pending", "paused", "cancelled", "interrupted"}
        )
        self.queue_view.retry_button.setVisible(queue_has_content and status == "failed")
        self.queue_view.restart_button.setVisible(
            queue_has_content and status in {"complete", "failed"}
        )
        header_mode = self._get("job_header_action_mode")
        header_enabled = {
            "open": not running and self.output_view.output_list.currentItem() is not None,
            "pause": running and has_job and status == "running",
            "retry": has_job and not running and status == "failed",
            "resume": has_job and not running and status in {"pending", "paused", "cancelled", "interrupted"},
            "run": not running and has_selected_scripts,
        }.get(header_mode, False)
        self.header_view.job_header_action.setEnabled(header_enabled)
        self.header_view.job_header_action.setToolTip(
            "Add at least one script to run this job."
            if header_mode == "run" and not has_selected_scripts
            else ""
        )
