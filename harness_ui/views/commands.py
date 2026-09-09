"""Global actions, menus, shortcuts, and button-role presentation."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import QMenu, QWidgetAction

from harness_ui.theme import ACCENT_COLORS, icon_button, set_button_role


class CommandViewBuilder:
    """Own command surfaces without leaking actions onto the main window."""

    def __init__(
        self,
        window,
        workspace,
        appearance_controller,
        settings_store,
    ):
        self.window = window
        self.workspace = workspace
        self.appearance = appearance_controller
        self.settings_store = settings_store
        self._worker_running = False
        self._selected_script_count = 0

    def build_actions(self):
        window = self.window
        settings_dock = self.workspace.settings.settings_dock
        logs_dock = self.workspace.logs.logs_dock
        self.action_new_job = QAction("New job", window)
        self.action_new_job.setShortcut(QKeySequence.StandardKey.New)
        self.action_add_scripts = QAction("Add scripts", window)
        self.action_add_scripts.setShortcut(QKeySequence.StandardKey.Open)
        self.action_save_script = QAction("Save script", window)
        self.action_save_script.setShortcut(QKeySequence.StandardKey.Save)
        self.action_run = QAction("Run job", window)
        self.action_run.setShortcut(QKeySequence("Ctrl+Return"))
        self.action_run.setToolTip("Run checked scripts (Ctrl+Enter)")
        self.action_refresh = QAction("Refresh", window)
        self.action_refresh.setShortcut(QKeySequence.StandardKey.Refresh)
        self.action_settings = QAction("Settings", window)
        self.action_settings.setCheckable(True)
        self.action_settings.setChecked(not settings_dock.isHidden())
        self.action_logs = QAction("Logs", window)
        self.action_logs.setCheckable(True)
        self.action_logs.setChecked(not logs_dock.isHidden())
        self.action_logs.setShortcut(QKeySequence("Ctrl+L"))
        self.action_preferences = QAction("Preferences…", window)
        self.action_preferences.setShortcut(QKeySequence("Ctrl+,"))
        self.action_shortcuts = QAction("Keyboard shortcuts", window)
        self.accent_menu = QMenu(window)
        self.accent_menu.setObjectName("accentMenu")
        self.accent_group = QActionGroup(self.accent_menu)
        self.accent_group.setExclusive(True)
        self.accent_actions = {}

        for name, color in ACCENT_COLORS.items():
            action = self.accent_menu.addAction(
                self.appearance.accent_icon(color),
                name.title(),
            )
            action.setCheckable(True)
            action.setData(name)
            action.setToolTip(color)
            action.triggered.connect(
                lambda checked=False, accent_name=name: (
                    self.appearance.set_accent(accent_name)
                )
            )
            self.accent_group.addAction(action)
            self.accent_actions[name] = action

        self.apply_button_hierarchy()
        self.appearance.set_accent(
            str(self.appearance.state.get("accent_name")),
            announce=False,
        )
        self.action_settings.toggled.connect(
            lambda visible: self.appearance.set_dock_visible(
                "settings",
                visible,
            )
        )
        self.action_logs.toggled.connect(
            lambda visible: self.appearance.set_dock_visible(
                "logs",
                visible,
            )
        )
        settings_dock.visibilityChanged.connect(
            lambda visible: self._sync_checkable(
                self.action_settings,
                visible,
            )
        )
        logs_dock.visibilityChanged.connect(
            lambda visible: self._sync_checkable(
                self.action_logs,
                visible,
            )
        )

        for action in (
            self.action_new_job,
            self.action_add_scripts,
            self.action_save_script,
            self.action_run,
            self.action_refresh,
            self.action_settings,
            self.action_logs,
            self.action_preferences,
        ):
            window.addAction(action)
        return self

    def render_generation_snapshot(self, snapshot):
        """Render global actions from generation state."""

        self._worker_running = bool(snapshot.worker_running)
        self._render_run_action()
        self.action_new_job.setEnabled(not self._worker_running)

    def render_script_snapshot(self, snapshot):
        """Render global script commands from script-document state."""

        self._selected_script_count = int(snapshot.selected_documents)
        self._render_run_action()
        self.action_save_script.setEnabled(bool(snapshot.has_current_document))

    def _render_run_action(self):
        """Keep the menu/shortcut Run command aligned with the header action."""

        enabled = not self._worker_running and bool(self._selected_script_count)
        self.action_run.setEnabled(enabled)
        if enabled:
            tool_tip = "Run checked scripts (Ctrl+Enter)"
        elif self._worker_running:
            tool_tip = "Pause or cancel the active job before starting another."
        else:
            tool_tip = "Add at least one script to run this job."
        self.action_run.setToolTip(tool_tip)

    @staticmethod
    def _sync_checkable(control, checked):
        checked = bool(checked)
        if control.isChecked() == checked:
            return
        control.blockSignals(True)
        control.setChecked(checked)
        control.blockSignals(False)

    def build_menu_bar(self):
        window = self.window
        scripts = self.workspace.scripts
        menu_bar = window._window_chrome.create_menu_bar()
        menu_bar.setObjectName("appMenuBar")
        menu_bar.setNativeMenuBar(False)
        self.app_menu_bar = menu_bar
        self.sidebar_toggle_button = icon_button(
            role="ghost",
            parent=menu_bar,
            object_name="sidebarToggleButton",
            icon_size=17,
            size=(32, 28),
            accessible_name="Toggle sidebar",
            tool_tip="Toggle sidebar (Ctrl+B)",
            checkable=True,
            auto_raise=True,
        )
        self.sidebar_toggle_button.setChecked(True)
        self.sidebar_toggle_widget_action = QWidgetAction(menu_bar)
        self.sidebar_toggle_widget_action.setDefaultWidget(
            self.sidebar_toggle_button
        )
        menu_bar.addAction(self.sidebar_toggle_widget_action)

        self.file_menu = menu_bar.addMenu("File")
        self.file_menu.setObjectName("appFileMenu")
        self.file_menu.addAction(self.action_new_job)
        self.file_menu.addAction(self.action_add_scripts)
        self.file_menu.addAction(self.action_save_script)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.action_run)
        self.edit_menu = menu_bar.addMenu("Edit")
        self.edit_menu.setObjectName("appEditMenu")
        self.edit_menu.addAction(self.action_save_script)
        self.edit_menu.addAction(scripts.script_line_numbers_action)
        self.view_menu = menu_bar.addMenu("View")
        self.view_menu.setObjectName("appViewMenu")
        self.sections_menu = self.view_menu.addMenu("Sections")
        self.sections_menu.setObjectName("appSectionsMenu")
        self.view_sidebar_action = QAction("Toggle sidebar", window)
        self.view_sidebar_action.setCheckable(True)
        self.view_sidebar_action.setChecked(True)
        self.view_sidebar_action.setShortcut(QKeySequence("Ctrl+B"))
        self.sections_menu.addAction(self.view_sidebar_action)
        self.sections_menu.addAction(self.action_settings)
        self.sections_menu.addAction(self.action_logs)
        self.view_menu.addAction(self.action_refresh)
        self.view_menu.addSeparator()
        self.view_accent_menu = self.view_menu.addMenu("Accent colour")
        self.view_accent_menu.setObjectName("viewAccentMenu")

        for action in self.accent_actions.values():
            self.view_accent_menu.addAction(action)

        self.settings_menu = menu_bar.addMenu("Settings")
        self.settings_menu.setObjectName("appSettingsMenu")
        self.settings_menu.addAction(self.action_preferences)
        self.help_menu = menu_bar.addMenu("Help")
        self.help_menu.setObjectName("appHelpMenu")
        self.help_menu.addAction(self.action_shortcuts)
        sidebar_visible = self.settings_store.value(
            "ui/sidebar_visible",
            True,
            type=bool,
        )
        self.appearance.set_sidebar_visible(
            sidebar_visible,
            persist=False,
        )
        return self

    def apply_button_hierarchy(self):
        workspace = self.workspace
        scripts = workspace.scripts
        queue = workspace.queue
        output = workspace.output
        logs = workspace.logs
        jobs = workspace.jobs
        header = workspace.header

        for button in (
            scripts.new_script_button,
            queue.pause_button,
            output.open_output_button,
            output.open_output_folder_button,
            queue.restart_button,
            output.play_button,
            output.play_segment_button,
            output.save_segment_button,
            logs.copy_logs_button,
            header.completion_review_button,
            scripts.save_as_button,
            scripts.script_menu_button,
        ):
            set_button_role(button, "neutral")

        for button in (
            jobs.new_job_button,
            jobs.search_jobs_button,
            jobs.refresh_jobs_button,
            logs.clear_logs_button,
        ):
            set_button_role(button, "ghost")

        for button in (
            header.completion_new_job_button,
            queue.resume_button,
            queue.retry_button,
            output.regenerate_button,
            header.job_header_action,
        ):
            set_button_role(button, "primary")

        for button in (
            scripts.delete_script_button,
            queue.cancel_button,
        ):
            set_button_role(button, "danger")


__all__ = ("CommandViewBuilder",)
