from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from modules.app_settings import (
    directory_size,
    migrate_library,
    migrate_model_cache,
)

class _MigrationTask(QObject):
    progress = Signal(int, int, int)
    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, kind, source, destination):
        super().__init__()
        self.kind = str(kind)
        self.source = Path(source)
        self.destination = Path(destination)

    def run(self):
        try:
            callback = lambda current, total, copied: self.progress.emit(
                int(current), int(total), int(copied)
            )
            operation = (
                migrate_library
                if self.kind == "library"
                else migrate_model_cache
            )
            report = operation(
                self.source,
                self.destination,
                progress_callback=callback,
            )
            self.succeeded.emit(report)
        except Exception as error:
            self.failed.emit(str(error))
        finally:
            self.finished.emit()


class _UsageTask(QObject):
    succeeded = Signal(dict)
    finished = Signal()

    def __init__(self, paths):
        super().__init__()
        self.paths = paths

    def run(self):
        library_usage = sum(
            directory_size(path)
            for path in (
                self.paths.input_root,
                self.paths.voices_root,
                self.paths.jobs_root,
                self.paths.outputs_root,
            )
        )
        values = {
            "Library": library_usage,
            "Models": directory_size(self.paths.model_cache_root),
            "Jobs": directory_size(self.paths.jobs_root),
            "Outputs": directory_size(self.paths.outputs_root),
            "Diagnostics": directory_size(self.paths.logs_root),
        }
        self.succeeded.emit(values)
        self.finished.emit()


class _TokenVerifyTask(QObject):
    succeeded = Signal(str)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, token):
        super().__init__()
        self.token = token

    def run(self):
        try:
            from huggingface_hub import HfApi

            result = HfApi(token=self.token).whoami()
            name = str(result.get("name") or result.get("fullname") or "account")
            self.succeeded.emit(f"Token verified for {name}.")
        except Exception as error:
            message = str(error).replace(str(self.token), "<redacted>")
            self.failed.emit(f"Token verification failed: {message}")
        finally:
            self.token = None
            self.finished.emit()
