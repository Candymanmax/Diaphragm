"""Search-palette and keyboard-shortcut dialog orchestration."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QEvent, QObject, QSize, Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidgetItem,
    QVBoxLayout,
)

from harness_ui.controllers.jobs import JobController
from harness_ui.dialogs import AppDialog, SearchDialog
from harness_ui.job_status import STATUS_COLORS
from harness_ui.state import UiStateStore
from harness_ui.theme import INLINE_SPACING, TEXT, TIGHT_SPACING
from modules.jobs import JobStoreError


@dataclass(frozen=True)
class SearchSnapshot:
    """Immutable description of the currently open search palette."""

    mode: str | None
    visible: bool
    result_count: int


class SearchController(QObject):
    """Own job search and keyboard-shortcut palette behavior."""

    snapshotChanged = Signal(object)

    def __init__(
        self,
        *,
        parent,
        state: UiStateStore,
        service,
        diagnostics_controller,
        job_controller,
        actions,
    ):
        super().__init__(parent)
        self.parent_window = parent
        self.state = state
        self.service = service
        self.diagnostics = diagnostics_controller
        self.job_controller = job_controller
        self.actions = tuple(actions)
        self._mode = None

    def _dialog(self):
        return self.state.get("job_search_dialog")

    def _set_dialog(self, dialog):
        self.state.set("job_search_dialog", dialog)

    def snapshot(self):
        dialog = self._dialog()
        return SearchSnapshot(
            mode=self._mode if dialog is not None else None,
            visible=bool(dialog is not None and dialog.isVisible()),
            result_count=(
                dialog.results.count() if dialog is not None else 0
            ),
        )

    def _publish_snapshot(self):
        self.snapshotChanged.emit(self.snapshot())

    def show_jobs(self):
        self.show_dialog(self.create_job_dialog())

    def show_shortcuts(self):
        self.show_dialog(self.create_shortcuts_dialog())

    def show_dialog(self, dialog):
        previous = self._dialog()

        if previous is not None and previous is not dialog:
            previous.reject()

        self._set_dialog(dialog)
        self._mode = dialog.mode
        application = QApplication.instance()

        if application is not None:
            application.installEventFilter(self)

        def clean_up(_result):
            if application is not None:
                application.removeEventFilter(self)

            if self._dialog() is dialog:
                self._set_dialog(None)
                self._mode = None
            self._publish_snapshot()

        dialog.finished.connect(clean_up)
        dialog.setWindowModality(Qt.WindowModality.NonModal)
        AppDialog.center_on_window(dialog, self.parent_window)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()
        self._publish_snapshot()

    def eventFilter(self, watched, event):
        dialog = self._dialog()

        if (
            dialog is not None
            and dialog.isVisible()
            and event.type() == QEvent.Type.MouseButtonPress
        ):
            global_position = event.globalPosition().toPoint()
            inside_dialog = dialog.rect().contains(
                dialog.mapFromGlobal(global_position)
            )

            if not inside_dialog:
                dialog.reject()
                return True

        return super().eventFilter(watched, event)

    def create_job_dialog(self):
        return self.create_dialog("jobs")

    def create_shortcuts_dialog(self):
        return self.create_dialog("shortcuts")

    def create_dialog(self, mode):
        shortcuts_mode = mode == "shortcuts"
        dialog = SearchDialog(mode, self.parent_window)

        if shortcuts_mode:
            dialog.queryChanged.connect(
                lambda query: self.populate_shortcut_results(
                    dialog.results,
                    query,
                )
            )
            self.populate_shortcut_results(dialog.results, "")
        else:
            dialog.queryChanged.connect(
                lambda query: self.populate_job_results(
                    dialog.results,
                    query,
                )
            )
            dialog.jobActivated.connect(
                lambda item: self.open_job_result(dialog, item)
            )
            self.populate_job_results(dialog.results, "")

        return dialog

    def shortcut_entries(self):
        entries = []

        for title, action in self.actions:
            shortcut = action.shortcut().toString(
                QKeySequence.SequenceFormat.NativeText
            )

            if shortcut:
                entries.append((title, shortcut))

        return entries

    def populate_shortcut_results(self, results, query):
        query = str(query).strip().lower()
        results.clear()
        matches = [
            (title, shortcut)
            for title, shortcut in self.shortcut_entries()
            if not query
            or query in title.lower()
            or query in shortcut.lower()
        ]

        if not matches:
            empty = QListWidgetItem("No matching shortcuts")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            results.addItem(empty)
            self._publish_snapshot()
            return

        for title, shortcut in matches:
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 40))
            item.setData(
                Qt.ItemDataRole.AccessibleTextRole,
                f"{title}, {shortcut}",
            )
            results.addItem(item)

            result_row = QFrame()
            result_row.setObjectName("jobSearchResultRow")
            result_layout = QHBoxLayout(result_row)
            result_layout.setContentsMargins(2, 1, 2, 1)
            result_layout.setSpacing(INLINE_SPACING)
            title_label = QLabel(title)
            title_label.setObjectName("jobSearchResultTitle")
            shortcut_label = QLabel(shortcut)
            shortcut_label.setObjectName("keyboardShortcutKey")
            shortcut_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            result_layout.addWidget(title_label, 1)
            result_layout.addWidget(shortcut_label)
            results.setItemWidget(item, result_row)

        results.setCurrentRow(-1)
        results.clearSelection()
        self._publish_snapshot()

    def searchable_jobs(self):
        jobs = []

        try:
            jobs = list(self.service.list_jobs(include_archived=True))
        except (JobStoreError, OSError) as error:
            self.diagnostics.append(str(error), "error")

        jobs_by_id = {
            str(manifest.get("job_id")): manifest
            for manifest in jobs
            if manifest.get("job_id")
        }
        for manifest in self.state.get("temporary_jobs").values():
            if manifest.get("job_id"):
                jobs_by_id[str(manifest["job_id"])] = manifest

        return list(jobs_by_id.values())

    def populate_job_results(self, results, query):
        query = str(query).strip().lower()
        results.clear()
        matches = []

        for manifest in self.searchable_jobs():
            haystack = JobController.display_name(manifest).lower()

            if query and query not in haystack:
                continue

            matches.append(manifest)

        if not matches:
            empty = QListWidgetItem("No matching jobs")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            results.addItem(empty)
            self._publish_snapshot()
            return

        for manifest in matches:
            status = str(manifest.get("status", "pending")).title()
            archived = "  ·  Archived" if manifest.get("archived") else ""
            title = JobController.display_name(manifest)
            accessible_text = f"{title}\n{status}{archived}"
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 54))
            item.setData(
                Qt.ItemDataRole.AccessibleTextRole,
                accessible_text,
            )
            item.setData(
                Qt.ItemDataRole.UserRole,
                str(manifest.get("job_id", "")),
            )
            item.setToolTip(f"{title}\n{manifest.get('job_id', '')}")
            results.addItem(item)

            result_row = QFrame()
            result_row.setObjectName("jobSearchResultRow")
            result_layout = QVBoxLayout(result_row)
            result_layout.setContentsMargins(2, 1, 2, 1)
            result_layout.setSpacing(TIGHT_SPACING)
            title_label = QLabel(title)
            title_label.setObjectName("jobSearchResultTitle")
            status_label = QLabel(f"{status}{archived}")
            status_label.setObjectName("jobSearchResultStatus")
            status_label.setStyleSheet(
                f"color: {STATUS_COLORS.get(status.lower(), TEXT)};"
            )
            result_layout.addWidget(title_label)
            result_layout.addWidget(status_label)
            results.setItemWidget(item, result_row)

        results.setCurrentRow(-1)
        results.clearSelection()
        self._publish_snapshot()

    def open_job_result(self, dialog, item):
        job_id = str(item.data(Qt.ItemDataRole.UserRole) or "")

        if not job_id:
            return

        self.state.set("current_job_id", job_id)
        self.job_controller.refresh(select_job_id=job_id)
        dialog.accept()


__all__ = ("SearchController", "SearchSnapshot")
