from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMainWindow

from harness_ui.application_wiring import ApplicationSignalWiring
from harness_ui.presenters import JobWorkspacePresenter
from harness_ui.controllers import (
    AppearanceController,
    DiagnosticsController,
    GenerationController,
    JobController,
    OutputReviewController,
    PreferencesController,
    SearchController,
    ShutdownController,
    ScriptDocumentController,
    StartupController,
)
from harness_ui.dialogs import NewJobDialog
from harness_ui.file_actions import atomic_write_text, move_to_trash
from harness_ui.state import UiStateStore
from harness_ui.title_bar import FramelessWindowController
from harness_ui.views import (
    AppearanceViewAdapter,
    CommandViewBuilder,
    WorkspaceFeedbackViewAdapter,
    WorkspaceViewBuilder,
)
from modules.app_settings import DiagnosticLogStore, SettingsRepository
from modules.service import TTSHarnessService
from modules.worker import JobWorkerProcess

class HarnessMainWindow(QMainWindow):
    def __init__(
        self,
        install_root=None,
        parent=None,
        *,
        settings_repository=None,
        app_paths=None,
    ):
        super().__init__(parent)
        self._window_chrome = FramelessWindowController(self)
        self.settings_repository = (
            settings_repository
            if settings_repository is not None
            else SettingsRepository.for_testing(install_root)
            if install_root is not None
            else SettingsRepository.for_application(
                Path(__file__).resolve().parents[1]
            )
        )
        self.paths = (
            app_paths
            if app_paths is not None
            else self.settings_repository.paths
        )
        self.project_root = self.paths.library_root
        self.service = TTSHarnessService(self.paths)
        self.service.ensure_project_folders()
        self.worker = JobWorkerProcess(self.paths)
        self.settings_store = self.settings_repository.settings
        preferences = self.settings_repository.preferences()
        self.log_store = DiagnosticLogStore(
            self.paths,
            retention_days=preferences.log_retention_days,
        )
        self.ui_state = UiStateStore(self)
        self.appearance_controller = AppearanceController(
            parent=self,
            state=self.ui_state,
            settings_repository=self.settings_repository,
            initial_accent=preferences.accent,
            status_message=lambda message, timeout: (
                self.statusBar().showMessage(message, timeout)
            ),
        )
        self.appearance_controller.apply_accent_stylesheet()

        self.setWindowTitle("Diaphragm")
        self.setMinimumSize(1000, 650)
        self.resize(1500, 900)
        self.setDockNestingEnabled(True)
        # Keep dock transitions synchronous. Native animated transitions can
        # otherwise overlap restored layout and visibility updates.
        self.setDockOptions(
            self.dockOptions() & ~QMainWindow.DockOption.AnimatedDocks
        )
        self.workspace_view = WorkspaceViewBuilder(
            self,
            self.ui_state,
            self.settings_store,
            self.service,
        ).build()
        self.command_view = CommandViewBuilder(
            self,
            self.workspace_view,
            self.appearance_controller,
            self.settings_store,
        )
        self.command_view.build_actions()
        self.appearance_view = AppearanceViewAdapter(
            self,
            self.workspace_view,
            self.command_view,
        )
        self.appearance_controller.bind_view(self.appearance_view)
        self.feedback_view = WorkspaceFeedbackViewAdapter(
            self.workspace_view.header,
        )
        self.script_controller = ScriptDocumentController(
            parent=self,
            view=self.workspace_view.scripts,
            state=self.ui_state,
            project_root=self.project_root,
            settings_repository=self.settings_repository,
            atomic_write_text=atomic_write_text,
            move_to_trash=move_to_trash,
            status_message=lambda message, timeout: (
                self.statusBar().showMessage(message, timeout)
            ),
        )
        self.autosave_timer = self.script_controller.autosave_timer
        self.diagnostics_controller = DiagnosticsController(
            parent=self,
            view=self.workspace_view.logs,
            state=self.ui_state,
            log_store=self.log_store,
        )
        self.output_controller = OutputReviewController(
            parent=self,
            view=self.workspace_view.output,
            state=self.ui_state,
            service=self.service,
            media_player=self.workspace_view.media_player,
            outputs_root=self.paths.outputs_root,
            worker_running=lambda: self.worker.running,
            append_log=self.diagnostics_controller.append,
            refresh_current_job=lambda force=False: (
                self.job_controller.refresh_current(force=force)
            ),
            start_worker=lambda mode: self.generation_controller.start(mode),
            status_message=lambda message, timeout: (
                self.statusBar().showMessage(message, timeout)
            ),
        )
        self.job_presenter = JobWorkspacePresenter(
            parent=self,
            workspace=self.workspace_view,
            state=self.ui_state,
            service=self.service,
            worker=self.worker,
            output_controller=self.output_controller,
            runtime_summary=GenerationController.runtime_summary,
            job_display_name=JobController.display_name,
        )
        self.job_controller = JobController(
            parent=self,
            workspace=self.workspace_view,
            state=self.ui_state,
            service=self.service,
            worker=self.worker,
            settings_panel=self.workspace_view.settings.settings_panel,
            diagnostics_controller=self.diagnostics_controller,
            output_controller=self.output_controller,
            presenter=self.job_presenter,
            settings_repository=self.settings_repository,
            prompt_job_name=lambda parent: NewJobDialog.prompt(parent),
            move_to_trash=move_to_trash,
            status_message=lambda message, timeout: (
                self.statusBar().showMessage(message, timeout)
            ),
        )
        self.generation_controller = GenerationController(
            parent=self,
            state=self.ui_state,
            service=self.service,
            worker=self.worker,
            script_controller=self.script_controller,
            output_controller=self.output_controller,
            diagnostics_controller=self.diagnostics_controller,
            settings_panel=self.workspace_view.settings.settings_panel,
            paths=self.paths,
            settings_repository=self.settings_repository,
            ensure_job=self.job_controller.new_job,
            job_display_name=JobController.display_name,
            refresh_jobs=self.job_controller.refresh,
            refresh_current_job=self.job_controller.refresh_current,
            status_message=lambda message, timeout: (
                self.statusBar().showMessage(message, timeout)
            ),
        )
        self.job_controller.bind_generation(self.generation_controller)
        self.command_view.build_menu_bar()
        self.search_controller = SearchController(
            parent=self,
            state=self.ui_state,
            service=self.service,
            diagnostics_controller=self.diagnostics_controller,
            job_controller=self.job_controller,
            actions=(
                ("New job", self.command_view.action_new_job),
                ("Add scripts", self.command_view.action_add_scripts),
                ("Save script", self.command_view.action_save_script),
                ("Run checked scripts", self.command_view.action_run),
                ("Refresh", self.command_view.action_refresh),
                ("Open Preferences", self.command_view.action_preferences),
                ("Toggle logs", self.command_view.action_logs),
                ("Toggle sidebar", self.command_view.view_sidebar_action),
            ),
        )
        self.preferences_controller = PreferencesController(
            parent=self,
            state=self.ui_state,
            settings_repository=self.settings_repository,
            service=self.service,
            log_store=self.log_store,
            worker=self.worker,
            model_busy=self.workspace_view.settings.settings_panel.model_controller.busy,
            settings_model_controller=(
                self.workspace_view.settings.settings_panel.model_controller
            ),
            script_controller=self.script_controller,
            set_accent=self.appearance_controller.set_accent,
            set_sidebar_visible=self.appearance_controller.set_sidebar_visible,
            set_dock_visible=self.appearance_controller.set_dock_visible,
            reset_window_layout=self.appearance_controller.reset_window_layout,
            status_message=lambda message, timeout: (
                self.statusBar().showMessage(message, timeout)
            ),
        )
        self.shutdown_controller = ShutdownController(
            parent=self,
            state=self.ui_state,
            service=self.service,
            worker=self.worker,
            script_controller=self.script_controller,
            output_controller=self.output_controller,
            appearance_controller=self.appearance_controller,
            focus_preferences=self.preferences_controller.focus,
            status_message=lambda message, timeout: (
                self.statusBar().showMessage(message, timeout)
            ),
        )
        self.signal_wiring = ApplicationSignalWiring(
            workspace=self.workspace_view,
            commands=self.command_view,
            state=self.ui_state,
            appearance=self.appearance_controller,
            appearance_view=self.appearance_view,
            feedback_view=self.feedback_view,
            jobs=self.job_controller,
            scripts=self.script_controller,
            generation=self.generation_controller,
            job_presenter=self.job_presenter,
            output=self.output_controller,
            diagnostics=self.diagnostics_controller,
            preferences=self.preferences_controller,
            search=self.search_controller,
        )
        self.signal_wiring.connect()
        self.startup_controller = StartupController(
            parent=self,
            project_root=self.project_root,
            service=self.service,
            script_controller=self.script_controller,
        )
        self.startup_controller.configurationLoaded.connect(
            self.workspace_view.settings.settings_panel.set_config
        )
        self.preferences_controller.modelRefreshRequested.connect(
            self.workspace_view.settings.settings_panel.model_controller.refresh
        )
        self.startup_controller.initialize()
        self.generation_controller.recover_interrupted_jobs()
        self.job_controller.refresh()
        self.appearance_controller.restore_window_state()

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(100)
        self.poll_timer.timeout.connect(self.generation_controller.poll)
        self.poll_timer.start()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.appearance_controller.handle_resize()

    def closeEvent(self, event):
        self.shutdown_controller.request_close(event)
