"""Storage usage, cleanup, and verified path migration operations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QFileDialog

from harness_ui.dialogs import AppDialog
from harness_ui.preferences.common import format_size, open_folder, set_feedback
from harness_ui.preferences.workers import _MigrationTask, _UsageTask


@dataclass(frozen=True)
class StoragePreferencesSnapshot:
    """Immutable state for storage operations and displayed paths."""

    library_root: Path
    model_cache_root: Path
    migration_active: bool
    background_tasks: int


class StoragePreferencesController(QObject):
    """Coordinate storage actions without coupling them to dialog lifecycle."""

    snapshotChanged = Signal(object)

    def __init__(
        self,
        *,
        dialog,
        repository,
        service,
        log_store,
        worker_running,
        task_registry,
    ):
        super().__init__(dialog)
        self.dialog = dialog
        self.repository = repository
        self.service = service
        self.log_store = log_store
        self.worker_running = worker_running
        self.task_registry = task_registry
        self._migration_active = False

    @property
    def migration_active(self):
        return self._migration_active

    def snapshot(self):
        return StoragePreferencesSnapshot(
            library_root=self.repository.paths.library_root,
            model_cache_root=self.repository.paths.model_cache_root,
            migration_active=self._migration_active,
            background_tasks=self.task_registry.snapshot().running,
        )

    def _publish_snapshot(self):
        self.snapshotChanged.emit(self.snapshot())

    def connect(self):
        dialog = self.dialog
        dialog.change_library_button.clicked.connect(self.change_library)
        dialog.open_library_button.clicked.connect(
            lambda: open_folder(self.repository.paths.library_root)
        )
        dialog.change_model_cache_button.clicked.connect(
            self.change_model_cache
        )
        dialog.open_model_cache_button.clicked.connect(
            lambda: open_folder(self.repository.paths.model_cache_root)
        )
        dialog.refresh_usage_button.clicked.connect(self.refresh_usage)
        dialog.clear_logs_button.clicked.connect(self.clear_logs)
        dialog.cleanup_temporary_button.clicked.connect(
            self.cleanup_temporary
        )

    def refresh_paths(self):
        self.dialog.library_path.setText(
            str(self.repository.paths.library_root)
        )
        self.dialog.model_cache_path.setText(
            str(self.repository.paths.model_cache_root)
        )
        self._publish_snapshot()

    def choose_folder(self, title, current):
        selected = QFileDialog.getExistingDirectory(
            self.dialog,
            title,
            str(current),
        )
        return Path(selected).resolve() if selected else None

    def change_library(self):
        destination = self.choose_folder(
            "Choose personal library",
            self.repository.paths.library_root,
        )

        if destination is not None:
            self.start_migration("library", destination)

    def change_model_cache(self):
        destination = self.choose_folder(
            "Choose model cache",
            self.repository.paths.model_cache_root,
        )

        if destination is not None:
            self.start_migration("model", destination)

    def start_migration(self, kind, destination):
        if self._migration_active:
            return

        dialog = self.dialog
        feedback = (
            dialog.library_feedback
            if kind == "library"
            else dialog.storage_feedback
        )
        progress = (
            dialog.library_progress
            if kind == "library"
            else dialog.model_cache_progress
        )

        if self.worker_running():
            set_feedback(
                feedback,
                "Finish or pause the active generation job before changing folders.",
                error=True,
            )
            return

        source = (
            self.repository.paths.library_root
            if kind == "library"
            else self.repository.paths.model_cache_root
        )

        if Path(source).resolve() == Path(destination).resolve():
            set_feedback(feedback, "That folder is already selected.")
            return

        if not AppDialog.confirm(
            dialog,
            "Copy local data",
            f"Copy data to:\n{destination}\n\n"
            "The current folder will remain untouched. Diaphragm must be "
            "restarted after the verified copy succeeds.",
            confirm_text="Copy data",
            cancel_text="Cancel",
            default_action="secondary",
        ):
            return

        self._migration_active = True
        progress.setRange(0, 0)
        progress.setValue(0)
        progress.show()
        set_feedback(feedback, "Preparing verified copy…")
        thread = QThread(dialog)
        task = _MigrationTask(kind, source, destination)
        task.moveToThread(thread)
        thread.started.connect(task.run)
        task.progress.connect(
            lambda current, total, copied: self.migration_progress(
                progress,
                current,
                total,
                copied,
            )
        )
        task.succeeded.connect(
            lambda report: self.migration_succeeded(
                kind,
                destination,
                feedback,
                progress,
                report,
            )
        )
        task.failed.connect(
            lambda message: set_feedback(feedback, message, error=True)
        )
        task.finished.connect(lambda: self.migration_finished(progress))
        task.finished.connect(thread.quit)
        task.finished.connect(task.deleteLater)
        self.task_registry.add(thread, task)
        thread.start()
        self._publish_snapshot()

    @staticmethod
    def migration_progress(progress, current, total, copied):
        progress.setRange(0, max(1, total))
        progress.setValue(current)
        progress.setFormat(
            f"{current}/{total} files · {format_size(copied)}"
        )

    def migration_succeeded(
        self,
        kind,
        destination,
        feedback,
        progress,
        report,
    ):
        if kind == "library":
            self.repository.set_library_root(destination)
        else:
            self.repository.set_model_cache_root(destination)
            self.dialog.model_manager.set_paths(self.repository.paths)

        self.refresh_paths()
        set_feedback(
            feedback,
            f"Verified {report.copied_files} copied files; "
            f"{report.skipped_files} identical files skipped. Restart Diaphragm "
            "to use the new folder.",
        )
        progress.setValue(progress.maximum())
        self.dialog.restartRequired.emit(kind)
        self.refresh_usage()

    def migration_finished(self, progress):
        self._migration_active = False
        progress.hide()
        self._publish_snapshot()

    def refresh_usage(self):
        dialog = self.dialog
        dialog.refresh_usage_button.setEnabled(False)
        dialog.storage_usage.setText("Calculating storage usage…")
        thread = QThread(dialog)
        task = _UsageTask(self.repository.paths)
        task.moveToThread(thread)
        thread.started.connect(task.run)
        task.succeeded.connect(self.usage_ready)
        task.finished.connect(thread.quit)
        task.finished.connect(task.deleteLater)
        thread.finished.connect(
            lambda: dialog.refresh_usage_button.setEnabled(True)
        )
        self.task_registry.add(thread, task)
        thread.start()
        self._publish_snapshot()

    def usage_ready(self, values):
        self.dialog.library_usage.setText(
            format_size(values.get("Library", 0))
        )
        self.dialog.storage_usage.setText(
            " · ".join(
                f"{name}: {format_size(size)}"
                for name, size in values.items()
                if name != "Library"
            )
        )
        self._publish_snapshot()

    def clear_logs(self):
        if AppDialog.confirm(
            self.dialog,
            "Clear diagnostic logs",
            "Remove local diagnostic log files? Personal library data is not affected.",
            confirm_text="Clear logs",
            cancel_text="Keep logs",
            confirm_role="danger",
            default_action="secondary",
        ):
            self.log_store.clear()
            set_feedback(
                self.dialog.storage_feedback,
                "Diagnostic logs cleared.",
            )
            self.refresh_usage()

    def cleanup_temporary(self):
        if not AppDialog.confirm(
            self.dialog,
            "Clean completed temporary files",
            "Remove eligible completed chunk and work files? Scripts, voices, "
            "jobs, models, and published outputs are kept.",
            confirm_text="Clean files",
            cancel_text="Cancel",
            confirm_role="danger",
            default_action="secondary",
        ):
            return

        failures = self.service.store.cleanup_completed_jobs()

        if failures:
            set_feedback(
                self.dialog.storage_feedback,
                f"Cleanup completed with {len(failures)} warning(s).",
                error=True,
            )
        else:
            set_feedback(
                self.dialog.storage_feedback,
                "Completed temporary files cleaned.",
            )

        self.refresh_usage()


__all__ = ("StoragePreferencesController", "StoragePreferencesSnapshot")
