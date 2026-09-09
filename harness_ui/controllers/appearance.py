"""Accent, panel visibility, tab selection, and persisted window layout."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from harness_ui.state import UiStateStore
from harness_ui.theme import (
    ACCENT_COLORS,
    SURFACE_2,
    build_stylesheet,
    normalize_accent_name,
)


# The dock tree and startup restoration path have changed enough that layouts
# written before the native-startup hardening must be treated as disposable UI
# state, not application data. Version 4 also skips layouts saved before the
# settings-header control was moved and converted to an icon-only button.
WINDOW_LAYOUT_SCHEMA_VERSION = 4
WINDOW_LAYOUT_KEYS = (
    "window/geometry",
    "window/state",
    "splitter/central",
    "splitter/scripts",
    "splitter/output",
    "splitter/segments",
)


@dataclass(frozen=True)
class AppearanceSnapshot:
    """Immutable state consumed by menu and Preferences observers."""

    accent: str
    sidebar_visible: bool
    settings_visible: bool
    logs_visible: bool
    active_tab: int


class AppearanceController(QObject):
    """Own appearance changes and all persistent workspace layout state."""

    snapshotChanged = Signal(object)
    panelRequested = Signal(str)

    def __init__(
        self,
        *,
        parent,
        state: UiStateStore,
        settings_repository,
        initial_accent,
        status_message,
    ):
        super().__init__(parent)
        self.parent_window = parent
        self.state = state
        self.settings_repository = settings_repository
        self.settings_store = settings_repository.settings
        self._status_message = status_message
        self.view_adapter = None
        self.state.set("accent_name", normalize_accent_name(initial_accent))

    def bind_view(self, view_adapter):
        """Attach the state-to-view adapter after the workspace is built."""

        self.view_adapter = view_adapter

    def snapshot(self):
        return AppearanceSnapshot(
            accent=str(self.state.get("accent_name")),
            sidebar_visible=bool(self.state.get("sidebar_visible")),
            settings_visible=bool(self.state.get("settings_visible")),
            logs_visible=bool(self.state.get("logs_visible")),
            active_tab=int(self.state.get("active_tab")),
        )

    def _publish_snapshot(self):
        self.snapshotChanged.emit(self.snapshot())

    @staticmethod
    def accent_icon(color):
        pixmap = QPixmap(14, 14)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor(SURFACE_2))
        painter.setBrush(QColor(color))
        painter.drawEllipse(1, 1, 12, 12)
        painter.end()
        return QIcon(pixmap)

    def apply_accent_stylesheet(self):
        application = QApplication.instance()

        if application is None:
            return

        accent = str(self.state.get("accent_name"))
        color = ACCENT_COLORS[accent]
        stylesheet = build_stylesheet(accent)

        if (
            application.property("ttsAccentName") == accent
            and application.property("ttsAccentColor") == color
            and application.styleSheet() == stylesheet
        ):
            return

        application.setProperty("ttsAccentName", accent)
        application.setProperty("ttsAccentColor", color)
        application.setStyleSheet(stylesheet)

    def set_accent(self, name, *, announce=True, persist=True):
        accent = normalize_accent_name(name)
        self.state.set("accent_name", accent)

        if persist:
            self.settings_repository.set_value("ui/accent", accent)

        self.apply_accent_stylesheet()

        if announce:
            self._status_message(
                f"Accent changed to {accent.title()}",
                3000,
            )
        self._publish_snapshot()

    def set_dock_visible(self, panel, visible, *, persist=True):
        visible = bool(visible)
        self.state.set(f"{panel}_visible", visible)

        if persist:
            self.settings_repository.set_value(
                f"ui/{panel}_visible",
                visible,
            )
        self._publish_snapshot()

    def request_panel(self, panel):
        """Reveal and focus a panel through the view adapter."""

        if panel not in {"settings", "logs"}:
            return
        self.set_dock_visible(panel, True, persist=False)
        self.panelRequested.emit(panel)

    def set_sidebar_visible(self, visible, *, persist=True):
        visible = bool(visible)
        self.state.set("sidebar_visible", visible)

        if persist:
            self.settings_repository.set_value(
                "ui/sidebar_visible",
                visible,
            )
        self._publish_snapshot()

    def set_work_tab(self, index):
        index = int(index)
        self.state.set("active_tab", index)
        self._publish_snapshot()

    def restore_window_state(self):
        preferences = self.settings_repository.preferences()
        if self.view_adapter is not None:
            self.view_adapter.restore_layout(
                self.settings_store,
                preferences,
                schema_version=WINDOW_LAYOUT_SCHEMA_VERSION,
                clear_layout=self.clear_saved_window_layout,
            )
        self.state.update(
            sidebar_visible=preferences.sidebar_visible,
            settings_visible=preferences.settings_visible,
            logs_visible=preferences.logs_visible,
        )
        self._publish_snapshot()
        if self.view_adapter is not None:
            self.view_adapter.enforce_size_constraints()

    def clear_saved_window_layout(self):
        for key in WINDOW_LAYOUT_KEYS:
            self.settings_store.remove(key)

    def reset_window_layout(self):
        self.clear_saved_window_layout()
        if self.view_adapter is not None:
            self.view_adapter.reset_layout(
                self.settings_store,
                schema_version=WINDOW_LAYOUT_SCHEMA_VERSION,
                clear_layout=lambda: None,
            )
        preferences = self.settings_repository.preferences()
        self.state.update(
            sidebar_visible=preferences.sidebar_visible,
            settings_visible=preferences.settings_visible,
            logs_visible=preferences.logs_visible,
        )
        self._status_message("Window layout reset", 3000)
        self._publish_snapshot()
        if self.view_adapter is not None:
            self.view_adapter.enforce_size_constraints()

    def save_window_state(self):
        if self.view_adapter is not None:
            self.view_adapter.save_layout(
                self.settings_store,
                schema_version=WINDOW_LAYOUT_SCHEMA_VERSION,
            )

    def handle_resize(self):
        if self.view_adapter is not None:
            self.view_adapter.handle_resize()


__all__ = (
    "AppearanceController",
    "AppearanceSnapshot",
    "WINDOW_LAYOUT_KEYS",
    "WINDOW_LAYOUT_SCHEMA_VERSION",
)
