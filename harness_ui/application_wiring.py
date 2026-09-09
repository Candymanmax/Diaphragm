"""Signal wiring for the composed desktop application."""

from __future__ import annotations


class ApplicationSignalWiring:
    """Connect typed workspace and command views to feature controllers."""

    def __init__(
        self,
        *,
        workspace,
        commands,
        state,
        appearance,
        appearance_view,
        feedback_view,
        jobs,
        scripts,
        generation,
        job_presenter,
        output,
        diagnostics,
        preferences,
        search,
    ):
        self.workspace = workspace
        self.commands = commands
        self.state = state
        self.appearance = appearance
        self.appearance_view = appearance_view
        self.feedback_view = feedback_view
        self.jobs = jobs
        self.scripts = scripts
        self.generation = generation
        self.job_presenter = job_presenter
        self.output = output
        self.diagnostics = diagnostics
        self.preferences = preferences
        self.search = search

    def connect(self):
        workspace = self.workspace
        commands = self.commands
        jobs_view = workspace.jobs
        header = workspace.header
        scripts_view = workspace.scripts
        queue = workspace.queue
        output_view = workspace.output
        logs = workspace.logs
        jobs = self.jobs
        scripts = self.scripts
        generation = self.generation
        output = self.output
        diagnostics = self.diagnostics
        appearance = self.appearance

        appearance.snapshotChanged.connect(self.appearance_view.render)
        appearance.panelRequested.connect(self.appearance_view.reveal_panel)
        self.appearance_view.render(appearance.snapshot())
        self.state.feedbackChanged.connect(self.feedback_view.render)
        self.feedback_view.render(
            None,
            self.state.get("workspace_error_message"),
        )
        generation.snapshotChanged.connect(
            self.job_presenter.render_generation_snapshot
        )
        generation.snapshotChanged.connect(commands.render_generation_snapshot)
        self.job_presenter.render_generation_snapshot(generation.snapshot())
        commands.render_generation_snapshot(generation.snapshot())
        scripts.snapshotChanged.connect(commands.render_script_snapshot)
        scripts.snapshotChanged.connect(self.job_presenter.render_script_snapshot)
        commands.render_script_snapshot(scripts.snapshot())
        self.job_presenter.render_script_snapshot(scripts.snapshot())
        generation.settingsRequested.connect(
            lambda: appearance.request_panel("settings")
        )
        generation.logsRequested.connect(
            lambda: appearance.request_panel("logs")
        )
        generation.tabRequested.connect(appearance.set_work_tab)
        jobs.tabRequested.connect(appearance.set_work_tab)

        jobs_view.new_job_button.clicked.connect(jobs.new_job)
        commands.action_new_job.triggered.connect(jobs.new_job)
        header.job_header_action.clicked.connect(jobs.header_action_triggered)
        header.completion_review_button.clicked.connect(
            lambda: self.appearance.set_work_tab(2)
        )
        header.completion_new_job_button.clicked.connect(jobs.new_job)
        jobs_view.jobs_button.clicked.connect(
            lambda checked=False: jobs.set_view(False)
        )
        jobs_view.archived_jobs_button.clicked.connect(
            lambda checked=False: jobs.set_view(True)
        )
        jobs_view.jobs_empty_state.actionRequested.connect(
            lambda state=jobs_view.jobs_empty_state: self.handle_empty_state_action(state)
        )
        header.settings_toggle_button.clicked.connect(
            lambda: appearance.set_dock_visible(
                "settings",
                not workspace.settings.settings_dock.isVisible(),
            )
        )
        workspace.settings.settings_dock.visibilityChanged.connect(
            self.appearance_view.render_settings_toggle
        )
        workspace.settings.settings_panel.configChanged.connect(
            jobs.settings_changed
        )
        commands.sidebar_toggle_button.toggled.connect(
            self.appearance.set_sidebar_visible
        )
        commands.view_sidebar_action.toggled.connect(
            self.appearance.set_sidebar_visible
        )

        for state_widget in (
            queue.queue_empty_state,
            output_view.output_empty_state,
            output_view.segment_empty_state,
            logs.logs_empty_state,
        ):
            state_widget.actionRequested.connect(
                lambda state=state_widget: self.handle_empty_state_action(state)
            )

        commands.action_add_scripts.triggered.connect(scripts.choose_files)
        scripts_view.new_script_button.clicked.connect(scripts.new_document)
        scripts_view.script_add_action.triggered.connect(scripts.choose_files)
        scripts_view.editor_empty_state.actionRequested.connect(
            scripts.new_document
        )
        scripts_view.editor_empty_state.secondaryActionRequested.connect(
            scripts.choose_files
        )
        scripts_view.delete_script_button.clicked.connect(
            scripts.delete_current
        )
        scripts_view.script_save_action.triggered.connect(scripts.save)
        scripts_view.save_as_button.clicked.connect(scripts.save_as)
        scripts_view.script_line_numbers_action.toggled.connect(
            scripts.set_line_numbers
        )
        commands.action_save_script.triggered.connect(scripts.save)

        commands.action_run.triggered.connect(generation.run_new_job)
        commands.action_refresh.triggered.connect(generation.refresh_all)
        commands.action_preferences.triggered.connect(self.preferences.show)
        jobs_view.search_jobs_button.clicked.connect(self.search.show_jobs)
        commands.action_shortcuts.triggered.connect(self.search.show_shortcuts)
        jobs_view.refresh_jobs_button.clicked.connect(generation.refresh_all)

        scripts_view.script_list.filesDropped.connect(scripts.add_dropped_paths)
        scripts_view.script_list.deleteRequested.connect(scripts.delete_row)
        scripts_view.editor_empty_state.filesDropped.connect(
            scripts.add_dropped_paths
        )
        scripts_view.script_list.currentItemChanged.connect(
            scripts.select_document
        )
        scripts_view.script_list.itemChanged.connect(scripts.update_summary)
        scripts_view.script_list.contentsCleared.connect(
            scripts.update_summary
        )
        scripts_view.script_list.customContextMenuRequested.connect(
            scripts.show_context_menu
        )
        scripts_view.script_editor.textChanged.connect(
            scripts.document_changed
        )
        header.work_tabs.currentChanged.connect(
            lambda index: self.state.set("active_tab", index)
        )
        jobs_view.job_list.currentItemChanged.connect(jobs.selected)
        jobs_view.job_list.customContextMenuRequested.connect(
            jobs.show_context_menu
        )

        queue.pause_button.clicked.connect(generation.pause)
        queue.cancel_button.clicked.connect(generation.cancel)
        queue.resume_button.clicked.connect(
            lambda: generation.start_existing("resume")
        )
        queue.retry_button.clicked.connect(
            lambda: generation.start_existing("retry")
        )
        queue.restart_button.clicked.connect(
            lambda: generation.start_existing("restart")
        )
        workspace.settings.settings_panel.configSaved.connect(
            self.preferences.config_saved
        )

        output_view.output_list.currentItemChanged.connect(
            output.select_output
        )
        output_view.play_button.clicked.connect(output.toggle_playback)
        workspace.media_player.positionChanged.connect(output.position_changed)
        workspace.media_player.durationChanged.connect(output.duration_changed)
        workspace.media_player.playbackStateChanged.connect(
            output.playback_state_changed
        )
        workspace.media_player.errorOccurred.connect(output.playback_error)
        output_view.position_slider.sliderMoved.connect(output.seek_slider)
        output_view.waveform.seekRequested.connect(output.seek_fraction)
        output_view.open_output_button.clicked.connect(
            output.open_selected_output
        )
        output_view.open_output_folder_button.clicked.connect(
            output.open_output_folder
        )
        output_view.segment_table.currentCellChanged.connect(
            output.select_segment
        )
        output_view.play_segment_button.clicked.connect(output.play_segment)
        output_view.save_segment_button.clicked.connect(
            output.save_segment_text
        )
        output_view.regenerate_button.clicked.connect(
            output.regenerate_segments
        )

        logs.log_filter.currentTextChanged.connect(diagnostics.set_filter)
        diagnostics.render()
        logs.clear_logs_button.clicked.connect(diagnostics.clear)
        logs.copy_logs_button.clicked.connect(diagnostics.copy)

    def handle_empty_state_action(self, state_widget):
        action = getattr(state_widget, "action_key", None)

        if action == "scripts":
            self.appearance.set_work_tab(0)
        elif action == "progress":
            self.appearance.set_work_tab(1)
        elif action == "settings":
            self.appearance.request_panel("settings")
        elif action == "all_logs":
            self.diagnostics.show_all_events()
        elif action == "new_job":
            self.jobs.new_job()
        elif action == "show_active_jobs":
            self.jobs.set_view(False)


__all__ = ("ApplicationSignalWiring",)
