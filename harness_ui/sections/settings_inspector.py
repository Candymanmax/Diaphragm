"""Fixed generation-settings inspector dock."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget

from harness_ui.sections.base import StatefulSection
from harness_ui.settings import SettingsPanel
from harness_ui.state import UiStateStore


SETTINGS_INSPECTOR_MIN_WIDTH = 360


class SettingsInspectorSection(StatefulSection):
    def __init__(self, state: UiStateStore, service, parent):
        super().__init__(state)
        self.settings_panel = SettingsPanel(service)
        self.settings_dock = QDockWidget("Job settings", parent)
        self.settings_dock.setObjectName("SettingsDock")
        self.settings_dock.setFeatures(
            QDockWidget.DockWidgetFeature.NoDockWidgetFeatures
        )
        self.settings_dock.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea
        )
        # Keep enough horizontal room for the longest labels and their
        # controls at normal and enlarged Windows scaling levels.
        self.settings_dock.setMinimumWidth(SETTINGS_INSPECTOR_MIN_WIDTH)
        self.settings_dock.setWidget(self.settings_panel)


__all__ = ("SettingsInspectorSection",)
