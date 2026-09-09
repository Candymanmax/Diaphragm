"""Job-header presentation rules."""

ACTIVE_PROGRESS_STATUSES = frozenset(
    {"splitting", "running", "generating", "pausing", "cancelling"}
)


class JobHeaderPresenter:
    """Render status, progress, and primary job action state."""

    def render_header_state(self, manifest, status, complete, total):
        scripts = manifest.get("scripts", [])
        if total:
            self.header_view.job_segment_count.setText(f"{complete}/{total} segments")
        else:
            complete_scripts = sum(
                script.get("status") == "complete" for script in scripts
            )
            self.header_view.job_segment_count.setText(
                f"{complete_scripts}/{len(scripts)} scripts"
                if scripts
                else "No segments"
            )

        self.header_view.completion_panel.setVisible(status == "complete")
        # The pipeline reports both splitting and generation through its active
        # states. Keep the progress row out of idle, draft, and terminal views
        # so an empty bar does not look like a broken or unfinished control.
        self.header_view.progress_panel.setVisible(
            status in ACTIVE_PROGRESS_STATUSES
        )
        if status == "complete":
            output_count = len(self.service.output_paths(manifest))
            self.header_view.completion_title.setText(
                "Generation complete" if output_count else "Generation finished"
            )
            output_text = (
                "output ready"
                if output_count == 1
                else f"{output_count} outputs ready"
                if output_count > 1
                else "output unavailable"
            )
            generated = (
                f"{complete} segments generated"
                if total
                else f"{len(scripts)} scripts generated"
            )
            self.header_view.completion_text.setText(f"{generated} · {output_text}")
            self.header_view.completion_review_button.setEnabled(output_count > 0)
            self.header_view.completion_new_job_button.setEnabled(not self.worker.running)
            self._set("job_header_action_mode", "open")
            self.header_view.job_header_action.setText("Open output")
        elif status in {"running", "pausing", "cancelling"}:
            self._set("job_header_action_mode", "pause")
            self.header_view.job_header_action.setText("Pause")
        elif status == "failed":
            self._set("job_header_action_mode", "retry")
            self.header_view.job_header_action.setText("Retry failed")
        elif status in {"pending", "paused", "cancelled", "interrupted"}:
            self._set("job_header_action_mode", "resume")
            self.header_view.job_header_action.setText("Resume")
        else:
            self._set("job_header_action_mode", "run")
            self.header_view.job_header_action.setText("Run job")
