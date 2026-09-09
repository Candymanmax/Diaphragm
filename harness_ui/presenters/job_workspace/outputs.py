"""Published-output presentation and empty states."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QListWidgetItem

from harness_ui.icons import lucide_icon
from harness_ui.theme import BLUE, RED, SUBTEXT_0, YELLOW


class JobOutputPresenter:
    """Render output files and output-specific empty states."""

    def render_outputs(self, manifest):
        selected_path = None
        current = self.output_view.output_list.currentItem()
        if current is not None:
            selected_path = current.data(Qt.ItemDataRole.UserRole)
        self.output_view.output_list.blockSignals(True)
        self.output_view.output_list.clear()
        output_paths = self.service.output_paths(manifest)
        for path in output_paths:
            item = QListWidgetItem(path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            item.setToolTip(str(path))
            self.output_view.output_list.addItem(item)
            if selected_path and str(path) == selected_path:
                self.output_view.output_list.setCurrentItem(item)
        if self.output_view.output_list.currentItem() is None and self.output_view.output_list.count():
            self.output_view.output_list.setCurrentRow(0)
        self.output_view.output_list.blockSignals(False)
        if self.output_view.output_list.currentItem() is not None and not self.worker.running:
            for button in self.output_view.output_action_buttons:
                button.show()
            self.output_view.output_stack.setCurrentWidget(self.output_view.output_content)
            self.output_controller.select_output(
                self.output_view.output_list.currentItem(), None
            )
        else:
            if not self.media_player.source().isEmpty():
                self.output_controller.release_media_source()
            self.show_output_state(manifest)

    def show_output_state(self, manifest=None):
        status = str((manifest or {}).get("status", "draft"))
        if manifest is None:
            state = (
                "No output yet",
                "Run a job, then return here to preview the generated audio.",
                "Go to scripts",
                lucide_icon("music-2", color=SUBTEXT_0, size=24),
                "scripts",
            )
        elif status in {"running", "pausing", "cancelling"}:
            state = (
                "Output is being prepared",
                "Published audio will appear here when generation finishes.",
                "View job progress",
                lucide_icon("loader-circle", color=BLUE, size=24),
                "progress",
            )
        elif status == "failed":
            state = (
                "No output was produced",
                "Review the failed segment details, then retry the job.",
                "View job progress",
                lucide_icon("triangle-alert", color=RED, size=24),
                "progress",
            )
        elif status == "complete":
            state = (
                "Published output not found",
                "The job finished, but no final audio is available. Review "
                "the job details before restarting it.",
                "View job progress",
                lucide_icon("triangle-alert", color=YELLOW, size=24),
                "progress",
            )
        else:
            state = (
                "Output not ready",
                "Start or resume this job to create its published audio.",
                "View job progress",
                lucide_icon("music-2", color=SUBTEXT_0, size=24),
                "progress",
            )
        title, message, action_text, icon, action_key = state
        for button in self.output_view.output_action_buttons:
            button.hide()
        self.output_view.output_empty_state.set_state(
            title, message, action_text, icon=icon, action_key=action_key
        )
        self.output_view.output_metadata.setText("Select an output to preview it")
        self.output_view.output_stack.setCurrentWidget(self.output_view.output_empty_state)
