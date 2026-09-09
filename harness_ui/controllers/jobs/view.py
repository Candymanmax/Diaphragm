"""Job list rendering and selection synchronization."""

import time

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QListWidgetItem

from harness_ui.job_status import STATUS_COLORS
from harness_ui.theme import TEXT
from harness_ui.widgets import JobCardWidget
from modules.jobs import JobStore, JobStoreError

from harness_ui.controllers.jobs.state import relative_time


class JobViewCommands:
    """Render job cards and keep selection/state in sync."""

    def reset_view(self, manifest=None):
        self._set(
            "current_job_id",
            manifest.get("job_id") if manifest is not None else None,
        )
        self._set("current_manifest", manifest)
        self._set("manifest_updated_at", None)
        self.jobs_view.job_list.clearSelection()
        self.jobs_view.job_list.setCurrentItem(None)
        self.sync_card_selection()
        self.presenter.reset_workspace(manifest)
        self.sync_settings_context(manifest)
        self.tabRequested.emit(0)
        if manifest is not None:
            self.presenter.render_manifest(manifest)
        else:
            self.presenter.update_controls()
        self._publish_snapshot()

    def set_view(self, archived):
        showing_archived = bool(archived)
        current_manifest = self._get("current_manifest") or {}
        current_archived = bool(current_manifest.get("archived", False))
        self._set("showing_archived_jobs", showing_archived)
        if current_manifest and current_archived != showing_archived:
            self.reset_view()
        self.refresh()

    def in_current_view(self, manifest):
        return bool(manifest.get("archived", False)) == bool(
            self._get("showing_archived_jobs")
        )

    def refresh(self, *args, select_job_id=None):
        del args
        preferred = select_job_id or self._get("current_job_id")
        try:
            jobs = self.service.list_jobs(
                include_archived=bool(self._get("showing_archived_jobs"))
            )
        except (JobStoreError, OSError) as error:
            self.diagnostics.append(str(error), "error")
            return

        jobs_by_id = {
            str(manifest.get("job_id")): manifest
            for manifest in jobs
            if manifest.get("job_id")
        }
        # The state cache gives the current session an immediate update while
        # the store remains the source of truth across application restarts.
        for manifest in self._get("temporary_jobs").values():
            if manifest.get("job_id"):
                jobs_by_id[str(manifest["job_id"])] = manifest
        jobs = list(jobs_by_id.values())
        visible_jobs = [
            manifest for manifest in jobs if self.in_current_view(manifest)
        ]
        visible_ids = {
            str(manifest["job_id"]) for manifest in visible_jobs
        }
        job_list = self.jobs_view.job_list
        existing = {}
        duplicate_indices = []
        for index in range(job_list.count()):
            item = job_list.item(index)
            job_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
            card = job_list.itemWidget(item)
            if not job_id or job_id in existing or card is None:
                duplicate_indices.append(index)
                continue
            existing[job_id] = (item, card)

        job_list.blockSignals(True)
        job_list.setUpdatesEnabled(False)
        try:
            for index in range(job_list.count() - 1, -1, -1):
                item = job_list.item(index)
                job_id = str(item.data(Qt.ItemDataRole.UserRole) or "")
                if job_id in visible_ids and index not in duplicate_indices:
                    continue
                card = job_list.itemWidget(item)
                job_list.setItemWidget(item, None)
                removed = job_list.takeItem(index)
                del removed
                if card is not None:
                    card.deleteLater()

            selected_item = None
            for target_index, manifest in enumerate(visible_jobs):
                job_id = str(manifest["job_id"])
                existing_entry = existing.get(job_id)
                if existing_entry is None:
                    item = QListWidgetItem()
                    item.setSizeHint(QSize(0, 60))
                    item.setData(Qt.ItemDataRole.UserRole, manifest["job_id"])
                    card = self._create_job_card(manifest)
                    card.archiveRequested.connect(self.toggle_archive)
                    card.contextMenuRequested.connect(self.show_context_menu)
                    job_list.insertItem(target_index, item)
                    job_list.setItemWidget(item, card)
                else:
                    item, card = existing_entry
                    current_index = job_list.row(item)
                    if current_index != target_index:
                        moved_item = job_list.takeItem(current_index)
                        job_list.insertItem(target_index, moved_item)
                        job_list.setItemWidget(moved_item, card)
                        item = moved_item

                    card.update_job(**self._job_card_values(manifest))

                if job_id == str(preferred):
                    selected_item = item
        finally:
            job_list.setUpdatesEnabled(True)
            job_list.blockSignals(False)

        visible_count = len(visible_jobs)

        self.jobs_view.set_empty_state(
            visible_count == 0,
            archived=bool(self._get("showing_archived_jobs")),
        )
        if selected_item is not None:
            self.jobs_view.job_list.setCurrentItem(selected_item)
        self.jobs_view.job_list.blockSignals(False)
        self.sync_card_selection()
        if selected_item is not None:
            selected_job_id = str(selected_item.data(Qt.ItemDataRole.UserRole))
            loaded_job_id = str((self._get("current_manifest") or {}).get("job_id", ""))
            if (
                self._get("current_job_id") != selected_job_id
                or loaded_job_id != selected_job_id
            ):
                self._set("current_job_id", selected_job_id)
                self._set("manifest_updated_at", None)
                self.refresh_current(force=True)
        self._set("last_job_refresh", time.monotonic())
        self._publish_snapshot()

    def _job_card_values(self, manifest):
        complete, total = JobStore.progress(manifest)
        status = (
            str(manifest.get("status", "pending")).strip().casefold()
            or "pending"
        )
        return {
            "title": self.display_name(manifest),
            "status": status,
            "relative_time": relative_time(
                manifest.get("updated_at") or manifest.get("created_at")
            ),
            "complete": complete,
            "total": total,
            "status_color": STATUS_COLORS.get(status, TEXT),
            "archived": bool(manifest.get("archived")),
            "archive_enabled": (
                not self.worker.running
                and status not in {"running", "pausing", "cancelling"}
            ),
        }

    def _create_job_card(self, manifest):
        return JobCardWidget(
            job_id=manifest["job_id"],
            **self._job_card_values(manifest),
        )

    def sync_card_selection(self):
        current = self.jobs_view.job_list.currentItem()
        for index in range(self.jobs_view.job_list.count()):
            item = self.jobs_view.job_list.item(index)
            card = self.jobs_view.job_list.itemWidget(item)
            if isinstance(card, JobCardWidget):
                card.set_selected(item is current)

    def selected(self, current, previous):
        for item, selected in ((previous, False), (current, True)):
            if item is None:
                continue
            card = self.jobs_view.job_list.itemWidget(item)
            if isinstance(card, JobCardWidget):
                card.set_selected(selected)
        if current is None:
            return
        job_id = current.data(Qt.ItemDataRole.UserRole)
        if not job_id:
            return
        self._set("current_job_id", str(job_id))
        self.refresh_current(force=True)
        self._publish_snapshot()

    def refresh_current(self, force=False):
        job_id = self._get("current_job_id")
        if not job_id:
            self.presenter.update_controls()
            return
        manifest = self._get("temporary_jobs").get(job_id)
        if manifest is None:
            try:
                manifest = self.service.load_job(job_id)
            except (JobStoreError, OSError) as error:
                self.diagnostics.append(str(error), "error")
                return
        if (
            not force
            and manifest.get("updated_at") == self._get("manifest_updated_at")
        ):
            return
        self._set("current_manifest", manifest)
        self._set("manifest_updated_at", manifest.get("updated_at"))
        self.sync_settings_context(manifest)
        self.presenter.render_manifest(manifest)
        self._publish_snapshot()
