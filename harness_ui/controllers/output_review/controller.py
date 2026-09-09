"""Composed output-review controller."""

from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QApplication

from harness_ui.controllers.output_review.playback import OutputPlaybackCommands
from harness_ui.controllers.output_review.segments import OutputSegmentCommands
from harness_ui.controllers.output_review.state import (
    OutputReviewSnapshot,
    is_playing_state,
)
from harness_ui.state import UiStateStore


class OutputReviewController(OutputPlaybackCommands, OutputSegmentCommands, QObject):
    """Coordinate output playback, segment editing, and regeneration."""

    snapshotChanged = Signal(object)

    def __init__(
        self,
        *,
        parent,
        view,
        state: UiStateStore,
        service,
        media_player,
        outputs_root,
        worker_running,
        append_log,
        refresh_current_job,
        start_worker,
        status_message,
    ):
        super().__init__(parent)
        self.parent_window = parent
        self.view = view
        self.state = state
        self.service = service
        self.media_player = media_player
        self.outputs_root = Path(outputs_root).resolve()
        self._worker_running = worker_running
        self._append_log = append_log
        self._refresh_current_job = refresh_current_job
        self._start_worker = start_worker
        self._status_message = status_message

    @property
    def current_manifest(self):
        return self.state.get("current_manifest")

    @current_manifest.setter
    def current_manifest(self, value):
        self.state.set("current_manifest", value)

    @property
    def current_segment(self):
        return self.state.get("current_segment")

    @current_segment.setter
    def current_segment(self, value):
        self.state.set("current_segment", value)

    def snapshot(self):
        item = self.view.output_list.currentItem()
        selected_output = (
            Path(item.data(Qt.ItemDataRole.UserRole)) if item is not None else None
        )
        segment = self.current_segment
        selected_segment = (
            (str(segment[0].get("id")), str(segment[1].get("id")))
            if segment
            else None
        )
        return OutputReviewSnapshot(
            selected_output=selected_output,
            selected_segment=selected_segment,
            playing=is_playing_state(self.media_player.playbackState()),
            position_ms=self.media_player.position(),
            duration_ms=self.media_player.duration(),
            worker_running=bool(self._worker_running()),
        )

    def _publish_snapshot(self):
        self.snapshotChanged.emit(self.snapshot())

    @staticmethod
    def _process_events():
        QApplication.processEvents()
