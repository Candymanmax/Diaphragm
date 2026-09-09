from __future__ import annotations

from PySide6.QtCore import QEvent, QPoint, QTimer, Qt, Signal
from PySide6.QtGui import QCursor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
)

from harness_ui.icons import lucide_icon
from harness_ui.job_status import display_status
from harness_ui.theme import (
    CONTROL_SPACING,
    MICRO_SPACING,
    OVERLAY_0,
    icon_button,
)


class JobCardWidget(QFrame):
    """Compact, non-interactive rendering for a persistent job row."""

    archiveRequested = Signal(str)
    contextMenuRequested = Signal(QPoint)

    def __init__(
        self,
        title,
        status,
        relative_time,
        complete,
        total,
        status_color,
        job_id="",
        archived=False,
        archive_enabled=True,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("jobCard")
        self.setProperty("selected", False)
        self.job_id = str(job_id)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setMouseTracking(True)

        status_key = str(status or "pending").strip().casefold()
        status_label = display_status(status_key)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(9, 4, 8, 4)
        layout.setSpacing(CONTROL_SPACING)

        details_layout = QVBoxLayout()
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(MICRO_SPACING)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(CONTROL_SPACING)
        self.status_indicator = QFrame()
        self.status_indicator.setObjectName("jobStatusIndicator")
        self.status_indicator.setFixedSize(8, 8)
        self.status_indicator.setStyleSheet(
            f"background: {status_color}; border-radius: 4px;"
        )
        self.status_indicator.setAccessibleName(
            f"{status_label} status"
        )
        self.status_indicator.setToolTip(f"Status: {status_label}")
        self.status_indicator.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )
        title_row.addWidget(self.status_indicator)
        self.title_label = QLabel(str(title))
        self.title_label.setObjectName("jobCardTitle")
        self.title_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        title_row.addWidget(self.title_label, 1)

        self.status_chip = QLabel(status_label)
        self.status_chip.setObjectName("jobStatusChip")
        self.status_chip.setProperty("status", status_key)
        self.status_chip.setAccessibleName(f"Status: {status_label}")
        self.status_chip.setToolTip(f"Status: {status_label}")
        self.status_chip.setSizePolicy(
            QSizePolicy.Policy.Maximum,
            QSizePolicy.Policy.Fixed,
        )
        title_row.addWidget(self.status_chip)

        self._archive_icon = lucide_icon(
            "archive", color=OVERLAY_0, size=16
        )
        blank_archive_pixmap = QPixmap(16, 16)
        blank_archive_pixmap.fill(Qt.GlobalColor.transparent)
        self._blank_archive_icon = QIcon(blank_archive_pixmap)
        archive_label = "Restore job" if archived else "Archive job"
        self.archive_button = icon_button(
            self._blank_archive_icon,
            role="ghost",
            parent=self,
            object_name="jobArchiveButton",
            icon_size=16,
            size=24,
            accessible_name=archive_label,
            auto_raise=True,
        )
        self.archive_button.setAccessibleName(archive_label)
        self.archive_button.setEnabled(bool(archive_enabled))
        self.archive_button.setProperty("hoverIconVisible", False)
        self.archive_button.setProperty("hoverHighlightVisible", False)
        self.archive_button.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )
        self.archive_button.installEventFilter(self)
        self.archive_button.clicked.connect(
            lambda: self.archiveRequested.emit(self.job_id)
        )
        details_layout.addLayout(title_row)

        progress_text = (
            f"{complete}/{total} segments" if total else "Waiting to split"
        )
        archived_text = " · Archived" if archived else ""
        self.meta_label = QLabel(
            f"{relative_time} · {progress_text}{archived_text}"
        )
        self.meta_label.setObjectName("jobCardMeta")
        details_layout.addWidget(self.meta_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("jobCardProgress")
        self.progress_bar.setRange(0, max(1, int(total)))
        self.progress_bar.setValue(int(complete))
        self.progress_bar.setTextVisible(False)
        details_layout.addWidget(self.progress_bar)

        layout.addLayout(details_layout, 1)
        layout.addWidget(self.archive_button, 0, Qt.AlignmentFlag.AlignVCenter)

    def update_job(
        self,
        *,
        title,
        status,
        relative_time,
        complete,
        total,
        status_color,
        archived=False,
        archive_enabled=True,
    ):
        """Update the rendered job without replacing this card widget."""

        status_key = str(status or "pending").strip().casefold() or "pending"
        status_label = display_status(status_key)

        self.title_label.setText(str(title))
        self.status_indicator.setStyleSheet(
            f"background: {status_color}; border-radius: 4px;"
        )
        self.status_indicator.setAccessibleName(
            f"{status_label} status"
        )
        self.status_indicator.setToolTip(f"Status: {status_label}")

        self.status_chip.setText(status_label)
        self.status_chip.setProperty("status", status_key)
        self.status_chip.setAccessibleName(f"Status: {status_label}")
        self.status_chip.setToolTip(f"Status: {status_label}")
        style = self.status_chip.style()
        if style is not None:
            style.unpolish(self.status_chip)
            style.polish(self.status_chip)

        progress_text = (
            f"{complete}/{total} segments" if total else "Waiting to split"
        )
        archived_text = " · Archived" if archived else ""
        self.meta_label.setText(
            f"{relative_time} · {progress_text}{archived_text}"
        )
        self.progress_bar.setRange(0, max(1, int(total)))
        self.progress_bar.setValue(int(complete))

        archive_label = "Restore job" if archived else "Archive job"
        self.archive_button.setAccessibleName(archive_label)
        self.archive_button.setEnabled(bool(archive_enabled))
        self._set_archive_hovered(False)
        self._set_archive_hovered(self._cursor_is_over_card())

    def _cursor_is_over_card(self):
        cursor_position = self.mapFromGlobal(QCursor.pos())
        return self.rect().contains(cursor_position)

    def _set_archive_hovered(self, hovered):
        hovered = bool(hovered and self.archive_button.isEnabled())
        self.archive_button.setIcon(
            self._archive_icon if hovered else self._blank_archive_icon
        )
        self.archive_button.setProperty("hoverIconVisible", hovered)
        self.archive_button.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            not hovered,
        )
        cursor_position = self.archive_button.mapFromGlobal(QCursor.pos())
        self._set_archive_highlighted(
            hovered and self.archive_button.rect().contains(cursor_position)
        )

    def _set_archive_highlighted(self, highlighted):
        highlighted = bool(
            highlighted
            and self.archive_button.isEnabled()
            and self.archive_button.property("hoverIconVisible")
        )
        self.archive_button.setProperty("hoverHighlightVisible", highlighted)
        # The archive button is deliberately made transparent until its card
        # is hovered.  When a refreshed card inherits that state without a
        # native enter event, repolish the button so the explicit hover
        # property updates its background and border as well as its icon.
        style = self.archive_button.style()
        if style is not None:
            style.unpolish(self.archive_button)
            style.polish(self.archive_button)
        self.archive_button.update()

    def eventFilter(self, watched, event):
        if watched is self.archive_button:
            if event.type() == QEvent.Type.Enter:
                self._set_archive_highlighted(True)
            elif event.type() == QEvent.Type.Leave:
                self._set_archive_highlighted(False)
        return super().eventFilter(watched, event)

    def _sync_archive_hover_state(self):
        """Restore hover feedback after the list replaces this card."""

        self._set_archive_hovered(self._cursor_is_over_card())

    def showEvent(self, event):
        super().showEvent(event)
        # A periodic job refresh can replace a card without moving the mouse,
        # so the replacement will not receive an enter event on its own.
        QTimer.singleShot(0, self._sync_archive_hover_state)

    def _job_list(self):
        widget = self.parentWidget()

        while widget is not None:
            if isinstance(widget, QListWidget):
                return widget
            widget = widget.parentWidget()

        return None

    def enterEvent(self, event):
        super().enterEvent(event)
        self._set_archive_hovered(True)

    def leaveEvent(self, event):
        # Moving from the card into its newly interactive child also emits a
        # leave event for the card. Keep the action visible during that handoff
        # so the pointer does not make the archive control disappear.
        cursor_position = self.mapFromGlobal(QCursor.pos())
        if self.rect().contains(cursor_position):
            super().leaveEvent(event)
            return

        self._set_archive_hovered(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        job_list = self._job_list()

        if job_list is not None:
            clear_keyboard_focus = getattr(
                job_list,
                "clear_keyboard_focus",
                None,
            )
            if clear_keyboard_focus is not None:
                clear_keyboard_focus()

            position = event.position().toPoint()
            # QListWidget item widgets are managed by the viewport and are
            # not always in a direct QObject parent chain.  Mapping through
            # global coordinates avoids Qt's parent-hierarchy warning.
            list_position = job_list.viewport().mapFromGlobal(
                self.mapToGlobal(position)
            )
            item = job_list.itemAt(list_position)

            if item is not None:
                job_list.setCurrentItem(item)

            if event.button() == Qt.MouseButton.RightButton:
                self.contextMenuRequested.emit(
                    list_position
                )
                event.accept()
                return

        super().mousePressEvent(event)

    def set_selected(self, selected):
        selected = bool(selected)

        if self.property("selected") == selected:
            return

        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
