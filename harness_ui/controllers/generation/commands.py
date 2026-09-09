"""Generation launch and user-command behavior."""

import shutil

from harness_ui.dialogs import AppDialog
from harness_ui.theme import YELLOW
from modules.jobs import JobStoreError
from modules.service import JobRequest


class GenerationCommands:
    """Validate settings and issue run/pause/cancel commands."""

    def run_new_job(self):
        if self.worker.running:
            AppDialog.information(
                self.parent_window,
                "Generation already running",
                "Pause or cancel the active job before starting another.",
            )
            return
        if not self._get("current_job_id") and not self._ensure_job():
            return
        scripts = self.script_controller.checked_paths_for_run()
        if scripts is None:
            return
        config = self.settings_panel.current_config()
        if config is None:
            self.settingsRequested.emit()
            return
        try:
            voice = self.service.resolve_voice(config.voice)
        except (FileNotFoundError, OSError) as error:
            self.settingsRequested.emit()
            AppDialog.critical(self.parent_window, "Voice reference unavailable", str(error))
            return

        disk_warning = ""
        try:
            free_bytes = shutil.disk_usage(self.paths.outputs_root).free
            warning_bytes = (
                self.settings_repository.preferences().low_disk_warning_gb * 1024 ** 3
            )
            if free_bytes < warning_bytes:
                disk_warning = (
                    "\n\nLow disk space: only "
                    f"{free_bytes / (1024 ** 3):.1f} GiB is available; "
                    "your warning threshold is "
                    f"{warning_bytes / (1024 ** 3):.0f} GiB."
                )
        except OSError:
            pass

        review = (
            f"Scripts: {len(scripts)}\n"
            f"Voice: {voice.name}\n"
            f"{self.settings_panel.summary()}\n\n"
            "Start this persistent job?"
            f"{disk_warning}"
        )
        if not AppDialog.confirm(
            self.parent_window,
            "Start generation",
            review,
            confirm_text="Start generation",
            cancel_text="Cancel",
            default_action="primary",
        ):
            return

        current_job_id = self._get("current_job_id")
        temporary_jobs = self._get("temporary_jobs")
        current_manifest = self._get("current_manifest") or {}
        temporary_job_id = (
            current_job_id
            if current_manifest.get("temporary")
            or current_job_id in temporary_jobs
            else None
        )
        job_name = self._job_display_name(current_manifest) if temporary_job_id else None
        try:
            manifest = self.service.create_job(
                JobRequest(
                    scripts=tuple(str(path) for path in scripts),
                    voice_override=str(voice),
                    name=job_name,
                ),
                config_override=config,
            )
        except Exception as error:
            AppDialog.critical(self.parent_window, "Could not create job", str(error))
            return
        if temporary_job_id:
            try:
                self.service.delete_draft(temporary_job_id)
            except (JobStoreError, OSError) as error:
                self.diagnostics.append(
                    f"Could not remove draft {temporary_job_id}: {error}",
                    "warning",
                )
            remaining_jobs = dict(temporary_jobs)
            remaining_jobs.pop(temporary_job_id, None)
            self._set("temporary_jobs", remaining_jobs)
        self._set("current_job_id", manifest["job_id"])
        self._set("current_manifest", manifest)
        self._set("manifest_updated_at", None)
        self._refresh_jobs(select_job_id=manifest["job_id"])
        self.start("prepared")

    def start(self, mode):
        job_id = self._get("current_job_id")
        if not job_id or self.worker.running:
            return
        self.output_controller.release_media_source()
        try:
            self.worker.start(job_id, mode=mode)
        except Exception as error:
            AppDialog.critical(self.parent_window, "Could not start worker", str(error))
            return
        self.settings_panel.set_job_scope(
            self._get("current_manifest"),
            editable=False,
            running=True,
        )
        self._set("worker_finished_handled", False)
        self._set("worker_return_code", None)
        self._set("runtime_summary", "Runtime metrics appear after model load")
        self._set("pause_requested", False)
        self._set("cancel_requested", False)
        self.tabRequested.emit(1)
        self._status_message("Generation worker is running", 0)
        self.diagnostics.append(f"Started isolated worker for {job_id} ({mode})")
        self._publish_snapshot()

    def start_existing(self, mode):
        if not self._get("current_job_id"):
            return
        if mode == "restart":
            if not AppDialog.confirm(
                self.parent_window,
                "Restart entire job",
                "This removes retained job audio and regenerates every "
                "segment. Published output remains until replacement. Continue?",
                confirm_text="Restart job",
                cancel_text="Cancel",
                confirm_role="danger",
                default_action="secondary",
                icon_name="triangle-alert",
                icon_color=YELLOW,
            ):
                return
        self.start(mode)

    def pause(self):
        job_id = self._get("current_job_id")
        if not job_id or not self.worker.running:
            return
        try:
            self.service.request_pause(job_id)
        except (JobStoreError, OSError) as error:
            AppDialog.critical(self.parent_window, "Could not pause job", str(error))
            return
        self._status_message("Pause requested; the active segment will finish first", 0)
        self.diagnostics.append("Pause requested", "warning")
        self._set("pause_requested", True)
        self._publish_snapshot()

    def cancel(self):
        job_id = self._get("current_job_id")
        if not job_id:
            return
        if not AppDialog.confirm(
            self.parent_window,
            "Cancel job",
            "Cancel after the active segment finishes? Completed segments will be preserved.",
            confirm_text="Cancel job",
            cancel_text="Keep running",
            confirm_role="danger",
            default_action="secondary",
            icon_name="triangle-alert",
            icon_color=YELLOW,
        ):
            return
        try:
            self.service.request_cancel(job_id)
        except (JobStoreError, OSError) as error:
            AppDialog.critical(self.parent_window, "Could not cancel job", str(error))
            return
        self._status_message("Cancel requested; the active segment will finish first", 0)
        self.diagnostics.append("Cancel requested", "warning")
        self._set("cancel_requested", True)
        self._publish_snapshot()

    def refresh_all(self):
        job_id = self._get("current_job_id")
        self._refresh_jobs(select_job_id=job_id)
        self._refresh_current_job(force=True)
        self._status_message("Refreshed", 2000)
