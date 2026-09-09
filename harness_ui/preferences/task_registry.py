"""Lifecycle registry for Preferences background tasks."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal


@dataclass(frozen=True)
class PreferenceTaskSnapshot:
    """Immutable summary of active Preferences work."""

    total: int
    running: int


class PreferenceTaskRegistry(QObject):
    """Keep QThread/task pairs alive and coordinate safe shutdown."""

    snapshotChanged = Signal(object)
    allFinished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries = []

    @property
    def entries(self):
        return tuple(self._entries)

    def snapshot(self):
        return PreferenceTaskSnapshot(
            total=len(self._entries),
            running=sum(
                thread.isRunning() for thread, _task in self._entries
            ),
        )

    def add(self, thread, task):
        self._entries.append((thread, task))
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self._forget(thread))
        self.snapshotChanged.emit(self.snapshot())

    def _forget(self, thread):
        self._entries = [
            entry for entry in self._entries if entry[0] is not thread
        ]
        snapshot = self.snapshot()
        self.snapshotChanged.emit(snapshot)

        if snapshot.running == 0:
            self.allFinished.emit()

    def has_running_tasks(self):
        return any(thread.isRunning() for thread, _task in self._entries)

    def stop_all(self, timeout_ms=5000):
        for thread, _task in self.entries:
            if thread.isRunning():
                thread.requestInterruption()
                thread.quit()

        for thread, _task in self.entries:
            if thread.isRunning() and not thread.wait(int(timeout_ms)):
                return False

        return True


__all__ = ("PreferenceTaskRegistry", "PreferenceTaskSnapshot")
