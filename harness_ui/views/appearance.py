"""Render appearance state into the composed workspace."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, Qt

from harness_ui.icons import lucide_icon
from harness_ui.theme import ACCENT_COLORS, SUBTEXT_0


class AppearanceViewAdapter:
    """Apply appearance snapshots without putting widget references in the controller."""

    def __init__(self, window, workspace, commands):
        self.window = window
        self.workspace = workspace
        self.commands = commands

    @staticmethod
    def _sync_checkable(control, checked):
        checked = bool(checked)
        if control.isChecked() == checked:
            return
        control.blockSignals(True)
        control.setChecked(checked)
        control.blockSignals(False)

    @staticmethod
    def _sync_dock_action(action, visible):
        AppearanceViewAdapter._sync_checkable(action, visible)

    @staticmethod
    def _set_dock_visibility(dock, visible):
        """Change explicit dock visibility only when its state differs."""

        visible = bool(visible)
        if dock.isHidden() == visible:
            dock.setVisible(visible)

    def render(self, snapshot):
        """Render the complete appearance snapshot as one idempotent update."""

        workspace = self.workspace
        commands = self.commands
        accent = str(snapshot.accent)

        for name, action in commands.accent_actions.items():
            action.setChecked(name == accent)
            action.setText(name.title())
            action.setIcon(
                commands.appearance.accent_icon(ACCENT_COLORS[name])
            )

        sidebar_visible = bool(snapshot.sidebar_visible)
        workspace.jobs.sidebar_panel.setVisible(sidebar_visible)
        if hasattr(commands, "sidebar_toggle_button"):
            icon_name = (
                "panel-left-close"
                if sidebar_visible
                else "panel-left-open"
            )
            action_name = "Hide sidebar" if sidebar_visible else "Show sidebar"
            commands.sidebar_toggle_button.setIcon(
                lucide_icon(icon_name, color=SUBTEXT_0, size=17)
            )
            commands.sidebar_toggle_button.setAccessibleName(action_name)
            commands.sidebar_toggle_button.setToolTip(
                f"{action_name} (Ctrl+B)"
            )
            self._sync_checkable(commands.sidebar_toggle_button, sidebar_visible)
            self._sync_checkable(commands.view_sidebar_action, sidebar_visible)

        self._sync_dock_action(commands.action_settings, snapshot.settings_visible)
        self._sync_dock_action(commands.action_logs, snapshot.logs_visible)
        self._set_dock_visibility(
            workspace.settings.settings_dock,
            snapshot.settings_visible,
        )
        self._set_dock_visibility(
            workspace.logs.logs_dock,
            snapshot.logs_visible,
        )
        self.render_settings_toggle(bool(snapshot.settings_visible))

        if workspace.header.work_tabs.currentIndex() != int(snapshot.active_tab):
            workspace.header.work_tabs.setCurrentIndex(int(snapshot.active_tab))

        # These widgets paint accent-dependent details outside the stylesheet.
        workspace.scripts.script_editor.line_number_area.update()
        workspace.output.waveform.update()
        workspace.jobs.job_list.viewport().update()

    def render_settings_toggle(self, visible):
        """Keep the header shortcut aligned with the dock's actual visibility."""

        button = self.workspace.header.settings_toggle_button
        visible = bool(visible)
        action = "Hide" if visible else "Show"
        label = f"{action} job settings inspector"
        button.setText("")
        button.setAccessibleName(f"{action} job settings inspector")
        button.setToolTip(label)

    def reveal_panel(self, panel):
        """Show and focus a requested dock without changing its ownership."""

        docks = {
            "settings": self.workspace.settings.settings_dock,
            "logs": self.workspace.logs.logs_dock,
        }
        dock = docks.get(str(panel))
        if dock is None:
            return
        dock.show()
        dock.raise_()

    def restore_layout(self, settings_store, preferences, *, schema_version, clear_layout):
        """Restore geometry and splitters; visibility is rendered from state."""

        try:
            saved_schema = int(
                settings_store.value("window/layout_schema", 0)
            )
        except (TypeError, ValueError):
            saved_schema = 0

        if saved_schema != schema_version:
            clear_layout()
            settings_store.setValue("window/layout_schema", schema_version)
            settings_store.sync()

        if preferences.restore_layout:
            geometry = settings_store.value("window/geometry")
            state = settings_store.value("window/state")

            if not self._restore_saved_layout_entry(
                geometry,
                self.window.restoreGeometry,
            ) or not self._restore_saved_layout_entry(
                state,
                self.window.restoreState,
            ):
                self._reset_invalid_layout(
                    settings_store,
                    schema_version=schema_version,
                    clear_layout=clear_layout,
                )
                return

        self._dock_to_fixed_area()

        if preferences.restore_layout:
            for splitter, key in self._splitter_values():
                value = settings_store.value(key)
                if not self._restore_saved_layout_entry(
                    value,
                    splitter.restoreState,
                ):
                    self._reset_invalid_layout(
                        settings_store,
                        schema_version=schema_version,
                        clear_layout=clear_layout,
                    )
                    return

    @staticmethod
    def _restore_saved_layout_entry(value, restore):
        """Restore one Qt byte payload and reject malformed settings values."""

        if value is None:
            return True

        if isinstance(value, QByteArray):
            payload = value
        elif isinstance(value, (bytes, bytearray)):
            payload = QByteArray(bytes(value))
        else:
            return False

        if payload.isEmpty():
            return False

        try:
            return bool(restore(payload))
        except (TypeError, RuntimeError):
            return False

    def _reset_invalid_layout(self, settings_store, *, schema_version, clear_layout):
        """Discard only invalid UI layout state and restore safe defaults."""

        clear_layout()
        self.reset_layout(
            settings_store,
            schema_version=schema_version,
            clear_layout=lambda: None,
        )

    def reset_layout(self, settings_store, *, schema_version, clear_layout):
        clear_layout()
        settings_store.setValue("window/layout_schema", schema_version)
        settings_store.sync()
        self.window.resize(1500, 900)
        self._dock_to_fixed_area()
        self.workspace.central_splitter.setSizes((285, 1000))
        self.workspace.scripts.script_splitter.setSizes((240, 900))
        self.workspace.output.output_splitter.setSizes((330, 400))
        self.workspace.output.segment_splitter.setSizes((700, 430))

    def save_layout(self, settings_store, *, schema_version):
        settings_store.setValue("window/layout_schema", schema_version)
        settings_store.setValue("window/geometry", self.window.saveGeometry())
        settings_store.setValue("window/state", self.window.saveState())
        for splitter, key in self._splitter_values():
            settings_store.setValue(key, splitter.saveState())
        settings_store.sync()

    def enforce_size_constraints(self):
        """Apply the existing compact-window safety rules."""

        settings_dock = self.workspace.settings.settings_dock
        logs_dock = self.workspace.logs.logs_dock
        if self.window.width() < 1200:
            settings_dock.hide()
        if self.window.height() < 760:
            logs_dock.hide()

    def handle_resize(self):
        settings_dock = self.workspace.settings.settings_dock
        logs_dock = self.workspace.logs.logs_dock
        if self.window.width() < 1120 and settings_dock.isVisible():
            settings_dock.hide()
        if self.window.height() < 680 and logs_dock.isVisible():
            logs_dock.hide()

    def _dock_to_fixed_area(self):
        settings_dock = self.workspace.settings.settings_dock
        logs_dock = self.workspace.logs.logs_dock
        self._ensure_dock_area(
            settings_dock,
            Qt.DockWidgetArea.RightDockWidgetArea,
        )
        self._ensure_dock_area(
            logs_dock,
            Qt.DockWidgetArea.BottomDockWidgetArea,
        )

    def _ensure_dock_area(self, dock, area):
        """Dock a panel once without rebuilding an already-correct layout item."""

        if self.window.dockWidgetArea(dock) != area:
            self.window.addDockWidget(area, dock)
        if dock.isFloating():
            dock.setFloating(False)

    def _splitter_values(self):
        return (
            (self.workspace.central_splitter, "splitter/central"),
            (self.workspace.scripts.script_splitter, "splitter/scripts"),
            (self.workspace.output.output_splitter, "splitter/output"),
            (self.workspace.output.segment_splitter, "splitter/segments"),
        )


__all__ = ("AppearanceViewAdapter",)
