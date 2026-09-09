"""Retained-segment presentation."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTableWidgetItem

from harness_ui.icons import lucide_icon
from harness_ui.job_status import STATUS_COLORS
from harness_ui.theme import BLUE, GREEN, RED, SUBTEXT_0, TEXT, YELLOW
from modules.jobs import JobStoreError


class JobSegmentPresenter:
    """Render segment tables and segment-review empty states."""

    def render_segments(self, manifest):
        rows = [
            (script, chunk)
            for script in manifest.get("scripts", [])
            for chunk in script.get("chunks", [])
        ]
        self.output_view.segment_table.blockSignals(True)
        self.output_view.segment_table.setRowCount(len(rows))
        for row, (script, chunk) in enumerate(rows):
            selector = QTableWidgetItem()
            selector.setFlags(
                Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            selector.setCheckState(Qt.CheckState.Unchecked)
            selector.setData(Qt.ItemDataRole.UserRole, (script.get("id"), chunk.get("id")))
            self.output_view.segment_table.setItem(row, 0, selector)
            values = (
                script.get("name", ""),
                chunk.get("id", ""),
                str(chunk.get("status", "pending")).title(),
                self.chunk_word_count(manifest, chunk),
                (
                    f"{float(chunk['elapsed_seconds']):.1f}s"
                    if chunk.get("elapsed_seconds") is not None
                    else "—"
                ),
            )
            for column, value in enumerate(values, start=1):
                item = QTableWidgetItem(str(value))
                if column == 3:
                    item.setForeground(QColor(STATUS_COLORS.get(chunk.get("status"), TEXT)))
                self.output_view.segment_table.setItem(row, column, item)
        self.output_view.segment_table.blockSignals(False)
        retained = bool(manifest.get("settings", {}).get("retain_job_artifacts", False))
        if retained and rows:
            for button in self.output_view.segment_action_buttons:
                button.show()
            self.output_view.segment_hint.setText(
                "Segment files retained; edit or select segments to regenerate."
            )
            self.output_view.segment_stack.setCurrentWidget(self.output_view.segment_splitter)
            self.output_view.segment_editor.setEnabled(True)
            self.output_view.play_segment_button.setEnabled(True)
            self.output_view.save_segment_button.setEnabled(True)
            self.output_view.regenerate_button.setEnabled(not self.worker.running)
        else:
            self.show_segment_state(manifest, retained=retained, has_rows=bool(rows))

    def show_segment_state(self, manifest=None, *, retained=False, has_rows=False):
        status = str((manifest or {}).get("status", "draft"))
        if manifest is None:
            self.output_view.segment_hint.setText(
                "Enable segment retention before running to edit or regenerate."
            )
            state = (
                "No segments to review",
                "Run a job with segment retention enabled to inspect and "
                "regenerate individual sections.",
                "Go to scripts",
                lucide_icon("list", color=SUBTEXT_0, size=24),
                "scripts",
            )
        elif not retained:
            self.output_view.segment_hint.setText(
                "Temporary segment files are removed after a successful job."
            )
            state = (
                "Segments were cleaned up" if status == "complete" else "Segment review is off",
                "The final output is still available. Enable Keep segment "
                "files for review before your next run to edit sections.",
                "Open settings",
                (
                    lucide_icon("check", color=GREEN, size=24)
                    if status == "complete"
                    else lucide_icon("list", color=SUBTEXT_0, size=24)
                ),
                "settings",
            )
        elif not has_rows:
            self.output_view.segment_hint.setText(
                "Retained segments will appear as generation progresses."
            )
            state = (
                "No retained segments found" if status == "complete" else "Segments will appear here",
                "Review job progress for the current generation state.",
                "View job progress",
                (
                    lucide_icon("loader-circle", color=BLUE, size=24)
                    if status != "complete"
                    else lucide_icon("triangle-alert", color=YELLOW, size=24)
                ),
                "progress",
            )
        else:
            return
        title, message, action_text, icon, action_key = state
        for button in self.output_view.segment_action_buttons:
            button.hide()
        self.output_view.segment_empty_state.set_state(
            title, message, action_text, icon=icon, action_key=action_key
        )
        self.output_view.segment_stack.setCurrentWidget(self.output_view.segment_empty_state)
        self.output_view.segment_editor.clear()
        self.output_view.segment_editor.setEnabled(False)
        self.output_view.play_segment_button.setEnabled(False)
        self.output_view.save_segment_button.setEnabled(False)
        self.output_view.regenerate_button.setEnabled(False)

    def chunk_word_count(self, manifest, chunk):
        try:
            path = self.service.store.resolve_artifact(manifest["job_id"], chunk.get("text_path"))
            if path is not None and path.is_file():
                return len(path.read_text(encoding="utf-8").split())
        except (JobStoreError, OSError, UnicodeError):
            pass
        return "—"
