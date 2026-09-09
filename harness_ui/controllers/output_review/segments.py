"""Retained segment selection, editing, and regeneration."""

from collections import defaultdict

import soundfile as sf
from PySide6.QtCore import Qt, QUrl

from harness_ui.dialogs import AppDialog
from harness_ui.theme import YELLOW
from modules.jobs import JobStoreError


class OutputSegmentCommands:
    """Edit retained segment text and prepare selective regeneration."""

    def select_segment(self, row, column, previous_row, previous_column):
        del column, previous_row, previous_column
        if row < 0 or not self.current_manifest:
            self.current_segment = None
            self.view.segment_editor.clear()
            self._publish_snapshot()
            return
        selector = self.view.segment_table.item(row, 0)
        if selector is None:
            return
        script_id, chunk_id = selector.data(Qt.ItemDataRole.UserRole)
        script = next(
            (
                entry
                for entry in self.current_manifest.get("scripts", [])
                if entry.get("id") == script_id
            ),
            None,
        )
        chunk = next(
            (
                entry
                for entry in (script or {}).get("chunks", [])
                if entry.get("id") == chunk_id
            ),
            None,
        )
        if script is None or chunk is None:
            return
        self.current_segment = (script, chunk)
        try:
            text_path = self.service.store.resolve_artifact(
                self.current_manifest["job_id"], chunk.get("text_path")
            )
            text = (
                text_path.read_text(encoding="utf-8")
                if text_path is not None and text_path.is_file()
                else ""
            )
        except (JobStoreError, OSError, UnicodeError):
            text = ""
        self.view.segment_editor.setPlainText(text)
        available = bool(text)
        self.view.save_segment_button.setEnabled(
            available and not self._worker_running()
        )
        self.view.play_segment_button.setEnabled(self.segment_audio_path() is not None)
        self._publish_snapshot()

    def segment_audio_path(self):
        if not self.current_manifest or not self.current_segment:
            return None
        _, chunk = self.current_segment
        try:
            path = self.service.store.resolve_artifact(
                self.current_manifest["job_id"], chunk.get("audio_path")
            )
        except JobStoreError:
            return None
        return path if path is not None and path.is_file() else None

    def play_segment(self):
        if self._worker_running():
            return
        path = self.segment_audio_path()
        if path is None:
            return
        self.media_player.stop()
        self.media_player.setSource(QUrl.fromLocalFile(str(path)))
        try:
            info = sf.info(path)
            duration = info.frames / info.samplerate if info.samplerate else 0
            self.view.output_metadata.setText(
                f"Segment preview · {duration:.1f}s · {info.samplerate:,} Hz"
            )
            self.view.waveform.set_file(path)
        except (OSError, RuntimeError, ValueError):
            pass
        self.media_player.play()

    def save_segment_text(self):
        if not self.current_manifest or not self.current_segment:
            return
        script, chunk = self.current_segment
        self.release_media_source()
        try:
            manifest = self.service.update_chunk_text(
                self.current_manifest["job_id"],
                script["id"],
                chunk["id"],
                self.view.segment_editor.toPlainText(),
            )
        except (JobStoreError, OSError) as error:
            AppDialog.critical(self.parent_window, "Could not save segment", str(error))
            return
        self.current_manifest = manifest
        self.state.set("manifest_updated_at", None)
        self._refresh_current_job(force=True)
        self._status_message(
            "Segment text saved; rebuild or regenerate to update audio", 5000
        )

    def selected_segment_groups(self):
        groups = defaultdict(list)
        for row in range(self.view.segment_table.rowCount()):
            item = self.view.segment_table.item(row, 0)
            if item is None or item.checkState() != Qt.CheckState.Checked:
                continue
            script_id, chunk_id = item.data(Qt.ItemDataRole.UserRole)
            groups[script_id].append(chunk_id)
        if not groups and self.current_segment:
            script, chunk = self.current_segment
            groups[script["id"]].append(chunk["id"])
        return groups

    def regenerate_segments(self):
        if not self.current_manifest or self._worker_running():
            return
        groups = self.selected_segment_groups()
        if not groups:
            AppDialog.information(
                self.parent_window,
                "No segments selected",
                "Check one or more segments, or select a segment row.",
            )
            return
        count = sum(len(values) for values in groups.values())
        if not AppDialog.confirm(
            self.parent_window,
            "Regenerate segments",
            f"Regenerate {count} selected segment(s) and rebuild the output?",
            confirm_text="Regenerate segments",
            cancel_text="Cancel",
            default_action="primary",
        ):
            return
        self.release_media_source()
        try:
            manifest = None
            for script_id, chunk_ids in groups.items():
                manifest = self.service.reset_chunks(
                    self.current_manifest["job_id"], script_id, chunk_ids
                )
        except (JobStoreError, OSError) as error:
            AppDialog.critical(
                self.parent_window,
                "Could not prepare regeneration",
                str(error),
            )
            return
        self.current_manifest = manifest
        self.state.set("manifest_updated_at", None)
        self._refresh_current_job(force=True)
        self._start_worker("prepared")
