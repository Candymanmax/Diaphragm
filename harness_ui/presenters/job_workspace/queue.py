"""Generation-queue presentation."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTreeWidgetItem

from harness_ui.icons import lucide_icon
from harness_ui.job_status import STATUS_COLORS
from harness_ui.theme import SUBTEXT_0, TEXT


class JobQueuePresenter:
    """Render script and segment progress into the queue tree."""

    def render_queue(self, manifest):
        expanded = {
            self.queue_view.queue_tree.topLevelItem(index).data(
                0,
                Qt.ItemDataRole.UserRole,
            )
            for index in range(self.queue_view.queue_tree.topLevelItemCount())
            if self.queue_view.queue_tree.topLevelItem(index).isExpanded()
        }
        self.queue_view.queue_tree.clear()
        scripts = manifest.get("scripts", [])
        if not scripts:
            for button in self.queue_view.queue_action_buttons:
                button.hide()
            self.queue_view.queue_empty_state.set_state(
                "No job details yet",
                "Add a script and start generation to build the job queue.",
                "Go to scripts",
                icon=lucide_icon("arrow-right", color=SUBTEXT_0, size=24),
                action_key="scripts",
            )
            self.queue_view.queue_stack.setCurrentWidget(self.queue_view.queue_empty_state)
            return

        self.queue_view.queue_stack.setCurrentWidget(self.queue_view.queue_tree)
        for script in scripts:
            chunks = script.get("chunks", [])
            completed = sum(chunk.get("status") == "complete" for chunk in chunks)
            script_item = QTreeWidgetItem(
                (
                    script.get("name", "Script"),
                    str(script.get("status", "pending")).title(),
                    "",
                    "",
                    script.get("error") or f"{completed}/{len(chunks)} segments",
                )
            )
            script_item.setData(0, Qt.ItemDataRole.UserRole, script.get("id"))
            script_item.setForeground(
                1,
                QColor(STATUS_COLORS.get(script.get("status"), TEXT)),
            )
            self.queue_view.queue_tree.addTopLevelItem(script_item)
            for chunk in chunks:
                elapsed = chunk.get("elapsed_seconds")
                child = QTreeWidgetItem(
                    (
                        chunk.get("id", "segment"),
                        str(chunk.get("status", "pending")).title(),
                        str(chunk.get("attempts", 0)),
                        f"{float(elapsed):.1f}s" if elapsed is not None else "—",
                        chunk.get("error") or "",
                    )
                )
                child.setForeground(
                    1,
                    QColor(STATUS_COLORS.get(chunk.get("status"), TEXT)),
                )
                script_item.addChild(child)
            script_item.setExpanded(
                script.get("id") in expanded
                or script.get("status") in {"running", "failed"}
            )
