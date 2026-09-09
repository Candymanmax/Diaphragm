"""Job-list context menu composition."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMenu

from harness_ui.dialogs import AppDialog
from modules.jobs import JobStoreError


class JobMenuCommands:
    """Build and show context-sensitive job actions."""

    @staticmethod
    def _named_menu_action(menu, text, object_name):
        action = menu.addAction(text)
        action.setObjectName(object_name)
        return action

    def _focus_context_job(self, job_id):
        """Keep an action tied to the card that opened its context menu."""

        job_id = str(job_id or "")
        if not job_id:
            return

        for index in range(self.jobs_view.job_list.count()):
            item = self.jobs_view.job_list.item(index)
            if str(item.data(Qt.ItemDataRole.UserRole) or "") == job_id:
                if self.jobs_view.job_list.currentItem() is not item:
                    self.jobs_view.job_list.setCurrentItem(item)
                break

        manifest = self._get("current_manifest") or {}
        if (
            self._get("current_job_id") != job_id
            or str(manifest.get("job_id") or "") != job_id
        ):
            self._set("current_job_id", job_id)
            self._set("manifest_updated_at", None)
            self.refresh_current(force=True)

    def _request_context_tab(self, job_id, tab_index):
        self._focus_context_job(job_id)
        self.tabRequested.emit(tab_index)

    def build_context_menu(self, manifest):
        menu = QMenu(self.jobs_view.job_list)
        menu.setObjectName("jobContextMenu")
        job_id = str(manifest.get("job_id") or "")
        temporary = bool(manifest.get("temporary", False))
        status = str(manifest.get("status", "pending"))
        active = status in {"running", "pausing", "cancelling"}
        progress_action = self._named_menu_action(
            menu, "View job progress", "jobContextProgress"
        )
        progress_action.triggered.connect(
            lambda checked=False: self._request_context_tab(job_id, 1)
        )
        # The review page also provides the correct empty state for a draft
        # job, so it remains available even before generation has started.
        review_action = self._named_menu_action(
            menu, "Review output", "jobContextReview"
        )
        review_action.setEnabled(not self.worker.running)
        review_action.triggered.connect(
            lambda checked=False: self._request_context_tab(job_id, 2)
        )
        if not temporary:
            output_folder_action = self._named_menu_action(
                menu, "Open output folder", "jobContextOutputFolder"
            )
            # The output directory is a valid destination before the first
            # output exists, so opening it should not depend on a file already
            # being present.
            output_folder_action.setEnabled(not self.worker.running)
            output_folder_action.triggered.connect(
                lambda checked=False: self.output_controller.open_output_folder()
            )

        menu.addSeparator()
        archive_text = "Restore job" if manifest.get("archived") else "Archive job"
        archive_action = self._named_menu_action(
            menu, archive_text, "jobContextArchive"
        )
        archive_action.setEnabled(not active and not self.worker.running)
        archive_action.triggered.connect(
            lambda checked=False: self.toggle_archive(job_id)
        )

        menu.addSeparator()
        delete_text = "Discard job…" if temporary else "Delete job…"
        delete_action = self._named_menu_action(
            menu, delete_text, "jobContextDelete"
        )
        delete_action.setToolTip(
            "Remove this unsaved draft from the job list"
            if temporary
            else "Move job history and cached data to the Recycle Bin"
        )
        delete_action.setEnabled(not active and not self.worker.running)
        delete_action.triggered.connect(
            lambda checked=False: self.delete(job_id)
        )
        return menu

    def show_context_menu(self, position):
        item = self.jobs_view.job_list.itemAt(position)
        if item is None:
            return
        self.jobs_view.job_list.setCurrentItem(item)
        job_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
        manifest = self._get("temporary_jobs").get(job_id)
        if manifest is None:
            try:
                manifest = self.service.load_job(job_id)
            except (JobStoreError, OSError) as error:
                AppDialog.critical(
                    self.parent_window,
                    "Could not open job menu",
                    str(error),
                )
                return
        menu = self.build_context_menu(manifest)
        menu.exec(self.jobs_view.job_list.viewport().mapToGlobal(position))
