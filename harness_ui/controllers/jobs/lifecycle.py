"""Job creation, startup, archive, and deletion commands."""

from pathlib import Path
from dataclasses import asdict

from PySide6.QtCore import Qt

from harness_ui.dialogs import AppDialog
from harness_ui.theme import RED
from modules.jobs import JobStoreError


class JobLifecycleCommands:
    """Own persistent and temporary job transitions."""

    def new_job(self):
        name, accepted = self._prompt_job_name(self.parent_window)
        if not accepted:
            return False
        name = str(name).strip()
        if not name:
            return False
        manifest = self.create_temporary_job(name)
        if manifest is None:
            return False
        self.reset_view(manifest)
        self.refresh(select_job_id=manifest["job_id"])
        return True

    def create_temporary_job(self, name):
        try:
            manifest = self.service.create_draft(name)
        except (JobStoreError, OSError) as error:
            AppDialog.critical(
                self.parent_window,
                "Could not create job",
                str(error),
            )
            return None

        # A draft owns its settings from the moment it is created. Seed it
        # from the private defaults file, not from whichever completed job
        # happened to be selected before the user clicked New job.
        try:
            manifest["settings"] = asdict(self.service.load_config())
            self.service.store.save(manifest)
        except (OSError, TypeError, ValueError) as error:
            self.diagnostics.append(
                f"Could not initialize draft settings: {error}",
                "error",
            )

        job_id = manifest["job_id"]
        temporary_jobs = dict(self._get("temporary_jobs"))
        temporary_jobs[job_id] = manifest
        self._set("temporary_jobs", temporary_jobs)
        return manifest

    def header_action_triggered(self):
        generation = self.generation_controller
        if generation is None:
            return
        mode = self._get("job_header_action_mode")
        if mode == "open":
            self.output_controller.open_selected_output()
        elif mode == "pause":
            generation.pause()
        elif mode == "retry":
            generation.start_existing("retry")
        elif mode == "resume":
            generation.start_existing("resume")
        else:
            generation.run_new_job()

    def initialize_startup_job(self):
        """Open the newest active job or show a blank draft."""

        if self._get("current_job_id") or self._get("temporary_jobs"):
            return
        if self._get("showing_archived_jobs"):
            self.set_view(False)
        if self.settings_repository.preferences().startup_behavior == "blank":
            self.reset_view()
            return
        first_item = self.jobs_view.job_list.item(0)
        if first_item is not None:
            job_id = str(first_item.data(Qt.ItemDataRole.UserRole) or "")
            if job_id:
                self.refresh(select_job_id=job_id)
                return
        self.reset_view()

    def is_temporary(self, job_id):
        job_id = str(job_id or "")
        cached = self._get("temporary_jobs").get(job_id)
        if cached is not None:
            return bool(cached.get("temporary", True))

        manifest = self._get("current_manifest") or {}
        return (
            str(manifest.get("job_id") or "") == job_id
            and bool(manifest.get("temporary", False))
        )

    def toggle_archive(self, job_id=None):
        selected_item = self.jobs_view.job_list.currentItem()
        selected_job_id = (
            str(selected_item.data(Qt.ItemDataRole.UserRole))
            if selected_item is not None
            else None
        )
        job_id = str(job_id or selected_job_id or self._get("current_job_id") or "")
        if not job_id:
            self._status_message("Select a job to archive", 3000)
            return
        try:
            manifest = self.service.load_job(job_id)
            archive = not manifest.get("archived", False)
            updated = self.service.set_archived(job_id, archive)
        except (JobStoreError, OSError) as error:
            AppDialog.critical(self.parent_window, "Could not update job", str(error))
            return

        if updated.get("temporary"):
            temporary_jobs = dict(self._get("temporary_jobs"))
            temporary_jobs[job_id] = updated
            self._set("temporary_jobs", temporary_jobs)

        job_leaves_current_view = bool(updated.get("archived", False)) != bool(
            self._get("showing_archived_jobs")
        )
        if job_leaves_current_view:
            if self._get("current_job_id") == job_id:
                self.reset_view()
            self.refresh()
        else:
            self._set("current_job_id", job_id)
            self._set("current_manifest", updated)
            self._set("manifest_updated_at", updated.get("updated_at"))
            self.refresh(select_job_id=job_id)
            self.presenter.render_manifest(updated)
        action = "Archived" if archive else "Restored"
        self._status_message(f"{action} job", 3000)
        self._publish_snapshot()

    def delete(self, job_id=None):
        selected_item = self.jobs_view.job_list.currentItem()
        if job_id is None and selected_item is None:
            self._status_message("Select a job to delete", 3000)
            return
        job_id = str(
            job_id
            or selected_item.data(Qt.ItemDataRole.UserRole)
            or self._get("current_job_id")
            or ""
        )
        if not job_id:
            self._status_message("Select a job to delete", 3000)
            return
        if self.is_temporary(job_id):
            try:
                self.service.delete_draft(job_id)
            except (JobStoreError, OSError) as error:
                AppDialog.critical(
                    self.parent_window,
                    "Could not discard draft",
                    str(error),
                )
                return
            temporary_jobs = dict(self._get("temporary_jobs"))
            temporary_jobs.pop(job_id, None)
            self._set("temporary_jobs", temporary_jobs)
            self.reset_view()
            self.refresh()
            self._status_message("Discarded draft", 3000)
            return
        try:
            manifest = self.service.load_job(job_id)
        except (JobStoreError, OSError) as error:
            AppDialog.critical(self.parent_window, "Could not delete job", str(error))
            return
        status = str(manifest.get("status", "pending"))
        if self.worker.running or status in {"running", "pausing", "cancelling"}:
            AppDialog.information(
                self.parent_window,
                "Job is active",
                "Pause or cancel the active job before deleting it.",
            )
            return
        names = [
            Path(script.get("name", "script")).stem
            for script in manifest.get("scripts", [])
        ]
        title = names[0] if len(names) == 1 else f"{len(names)} scripts"
        if not AppDialog.confirm(
            self.parent_window,
            "Move job to Recycle Bin",
            f"Delete the job '{title}' and its cached job data?\n\n"
            "The job folder will be moved to the Recycle Bin. Published "
            "audio in the final folder will be kept.",
            confirm_text="Move to Recycle Bin",
            cancel_text="Cancel",
            confirm_role="danger",
            icon_name="trash-2",
            icon_color=RED,
        ):
            return
        job_folder = self.service.store.job_folder(job_id)
        try:
            moved = job_folder.exists() and self._move_to_trash(job_folder)
        except OSError as error:
            AppDialog.critical(self.parent_window, "Could not delete job", str(error))
            return
        if not moved:
            AppDialog.critical(
                self.parent_window,
                "Could not delete job",
                "Windows could not move the job to the Recycle Bin. "
                "The job was left unchanged.",
            )
            return
        self.reset_view()
        self.refresh()
        self._status_message(
            f"Moved job '{title}' to the Recycle Bin; output files kept",
            5000,
        )
