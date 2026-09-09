"""Feature-specific desktop GUI tests."""

from tests.desktop_base import *
from PySide6.QtCore import QProcess

class DesktopWorkspaceTests(DesktopHarnessBase):
    def test_dock_layout_updates_are_synchronous_and_idempotent(self):
        self.window = HarnessMainWindow(self.root)
        appearance = self.window.appearance_view
        settings_dock = self.window.workspace_view.settings.settings_dock
        logs_dock = self.window.workspace_view.logs.logs_dock

        self.assertFalse(
            self.window.dockOptions()
            & QMainWindow.DockOption.AnimatedDocks
        )

        for _ in range(25):
            appearance._dock_to_fixed_area()
            appearance._set_dock_visibility(settings_dock, False)
            appearance._set_dock_visibility(settings_dock, True)
            appearance._set_dock_visibility(logs_dock, True)
            appearance._set_dock_visibility(logs_dock, False)
            self.application.processEvents()

        self.assertEqual(
            self.window.dockWidgetArea(settings_dock),
            Qt.DockWidgetArea.RightDockWidgetArea,
        )
        self.assertEqual(
            self.window.dockWidgetArea(logs_dock),
            Qt.DockWidgetArea.BottomDockWidgetArea,
        )
        self.assertFalse(settings_dock.isFloating())
        self.assertFalse(logs_dock.isFloating())


    def test_responsive_shell_exposes_core_workflows(self):
        self.window = HarnessMainWindow(self.root)
        self.window.show()
        self.application.processEvents()

        self.assertGreaterEqual(self.window.minimumWidth(), 1000)
        self.assertGreaterEqual(self.window.minimumHeight(), 650)
        self.assertEqual(self.window.workspace_view.header.work_tabs.count(), 3)
        self.assertEqual(self.window.workspace_view.header.work_tabs.objectName(), "workTabs")
        self.assertTrue(self.window.workspace_view.settings.settings_dock.isVisible())
        self.assertEqual(
            self.window.workspace_view.settings.settings_dock.windowTitle(),
            "Job settings",
        )
        self.assertFalse(
            any(
                label.text() == "Configuration"
                for label in self.window.workspace_view.settings.settings_panel.findChildren(QLabel)
            )
        )
        panel = self.window.workspace_view.settings.settings_panel
        self.assertEqual(
            panel.findChild(QLabel, "settingsScopeHint").text(),
            "These settings apply to the next new job. Save them as defaults for future jobs.",
        )
        self.assertEqual(panel.save_button.text(), "Save as defaults")
        self.assertTrue(panel.job_editable)
        self.assertEqual(panel.toolbox.objectName(), "settingsToolbox")
        self.assertEqual(panel.generation_page.objectName(), "settingsSectionPage")
        self.assertIn(
            "Automatic adapts section sizes; manual uses the limit below.",
            [label.text() for label in panel.findChildren(QLabel, "settingsHelper")],
        )
        self.assertGreaterEqual(
            self.window.workspace_view.settings.settings_dock.minimumWidth(),
            360,
        )
        self.assertFalse(self.window.workspace_view.logs.logs_dock.isVisible())
        self.assertEqual(self.window.workspace_view.scripts.script_list.count(), 1)
        self.assertEqual(len(self.window.script_controller.checked_paths()), 1)
        self.assertEqual(
            self.window.workspace_view.settings.settings_panel.to_config().model,
            "original",
        )

        self.window.resize(1050, 680)
        self.application.processEvents()
        self.assertFalse(self.window.workspace_view.settings.settings_dock.isVisible())

        self.window.workspace_view.settings.settings_dock.show()
        self.application.processEvents()
        self.assertTrue(self.window.workspace_view.settings.settings_dock.isVisible())


    def test_incompatible_saved_layout_is_discarded_before_restore(self):
        settings = QSettings(
            str(self.root / "test-settings.ini"),
            QSettings.Format.IniFormat,
        )
        settings.setValue("window/layout_schema", 0)

        for key in WINDOW_LAYOUT_KEYS:
            settings.setValue(key, QByteArray(b"incompatible-layout"))

        settings.sync()
        self.window = HarnessMainWindow(self.root)

        self.assertEqual(
            self.window.settings_store.value(
                "window/layout_schema",
                type=int,
            ),
            WINDOW_LAYOUT_SCHEMA_VERSION,
        )

        for key in WINDOW_LAYOUT_KEYS:
            self.assertFalse(self.window.settings_store.contains(key))

        self.window.appearance_controller.save_window_state()

        for key in WINDOW_LAYOUT_KEYS:
            self.assertTrue(self.window.settings_store.contains(key))

    def test_malformed_saved_layout_is_reset_without_touching_project_data(self):
        jobs_root = self.root / "jobs"
        jobs_root.mkdir(exist_ok=True)
        marker = jobs_root / "keep.txt"
        marker.write_text("keep", encoding="utf-8")
        settings = QSettings(
            str(self.root / "test-settings.ini"),
            QSettings.Format.IniFormat,
        )
        settings.setValue("window/layout_schema", WINDOW_LAYOUT_SCHEMA_VERSION)
        settings.setValue("window/geometry", "not-a-qt-byte-array")
        settings.setValue("window/state", QByteArray())
        settings.setValue("splitter/central", QByteArray(b"broken"))
        settings.sync()

        self.window = HarnessMainWindow(self.root)

        self.assertEqual(marker.read_text(encoding="utf-8"), "keep")
        self.assertEqual(
            self.window.settings_store.value(
                "window/layout_schema",
                type=int,
            ),
            WINDOW_LAYOUT_SCHEMA_VERSION,
        )
        for key in WINDOW_LAYOUT_KEYS:
            self.assertFalse(self.window.settings_store.contains(key))


    def test_settings_headers_fit_without_horizontal_overflow(self):
        self.window = HarnessMainWindow(self.root)
        self.window.show()
        self.application.processEvents()

        panel = self.window.workspace_view.settings.settings_panel
        headers = [
            button
            for button in panel.toolbox.findChildren(QAbstractButton)
            if button.parent() is panel.toolbox
        ]

        self.assertEqual(len(headers), 3)

        for header in headers:
            self.assertGreaterEqual(header.height(), 36)
            self.assertGreater(header.height(), header.fontMetrics().height())

        self.assertEqual(panel.scroll.horizontalScrollBar().maximum(), 0)
        self.assertLessEqual(
            panel.scroll.widget().width(),
            panel.scroll.viewport().width(),
        )


    def test_model_settings_hide_unsupported_rows(self):
        self.window = HarnessMainWindow(self.root)
        panel = self.window.workspace_view.settings.settings_panel

        def choose(model_id):
            panel.model.setCurrentIndex(panel.model.findData(model_id))
            self.application.processEvents()

        def row_hidden(form, field):
            return field.isHidden() and form.labelForField(field).isHidden()

        choose("original")
        self.assertTrue(row_hidden(panel.primary_form, panel.language))
        self.assertTrue(row_hidden(panel.generation_form, panel.top_k))
        self.assertFalse(panel.exaggeration.isHidden())
        self.assertFalse(panel.preset.isHidden())
        original_toolbox_height = panel.toolbox.height()

        choose("turbo")
        for field in (panel.exaggeration, panel.cfg_weight, panel.min_p):
            self.assertTrue(row_hidden(panel.generation_form, field))

        for field in (
            panel.temperature,
            panel.repetition_penalty,
            panel.top_p,
            panel.top_k,
        ):
            self.assertFalse(field.isHidden())

        self.assertTrue(row_hidden(panel.primary_form, panel.preset))
        turbo_toolbox_height = panel.toolbox.height()
        self.assertLess(turbo_toolbox_height, original_toolbox_height)
        headers = [
            button
            for button in panel.toolbox.findChildren(QAbstractButton)
            if button.parent() is panel.toolbox
        ]
        expected_height = (
            panel.generation_form.sizeHint().height()
            + sum(
                max(button.minimumHeight(), button.sizeHint().height())
                for button in headers
            )
            + 4
        )
        self.assertEqual(turbo_toolbox_height, expected_height)

        choose("v3")
        self.assertFalse(panel.language.isHidden())
        self.assertFalse(
            panel.primary_form.labelForField(panel.language).isHidden()
        )
        self.assertFalse(panel.preset.isHidden())
        self.assertTrue(row_hidden(panel.generation_form, panel.top_k))

        choose("nano")
        self.assertTrue(row_hidden(panel.primary_form, panel.language))
        self.assertTrue(row_hidden(panel.primary_form, panel.preset))
        self.assertTrue(row_hidden(panel.generation_form, panel.cfg_weight))
        self.assertFalse(panel.top_k.isHidden())


    def test_generation_controls_use_conservative_ranges(self):
        self.window = HarnessMainWindow(self.root)
        panel = self.window.workspace_view.settings.settings_panel

        expected_ranges = {
            "exaggeration": (0.0, 1.0),
            "cfg_weight": (0.0, 1.0),
            "temperature": (0.1, 1.5),
            "repetition_penalty": (1.0, 2.0),
            "min_p": (0.0, 0.2),
            "top_p": (0.1, 1.0),
            "top_k": (1, 1000),
        }

        for field, (minimum, maximum) in expected_ranges.items():
            with self.subTest(field=field):
                widget = getattr(panel, field)
                self.assertAlmostEqual(widget.minimum(), minimum)
                self.assertAlmostEqual(widget.maximum(), maximum)

        expected_labels = {
            "exaggeration": "Emotion intensity",
            "cfg_weight": "Guidance strength",
            "temperature": "Delivery variation",
            "repetition_penalty": "Repetition control",
            "min_p": "Rare-choice cutoff",
            "top_p": "Likely-choice range",
            "top_k": "Choice limit",
        }

        for field, expected_label in expected_labels.items():
            widget = getattr(panel, field)
            label = panel.generation_form.labelForField(widget)
            self.assertEqual(label.text(), expected_label)
            self.assertEqual(widget.accessibleName(), expected_label)
            self.assertEqual(widget.toolTip(), "")
            self.assertIn(f"<b>{expected_label}</b>", label.toolTip())
            self.assertIn("<br>", label.toolTip())
            self.assertIn("Allowed range:", label.toolTip())
            self.assertNotIn(
                "Values outside this range",
                label.toolTip(),
            )

        self.assertEqual(panel.toolbox.itemText(0), "Voice Generation")
        self.assertEqual(panel.toolbox.itemText(1), "Text Splitting")
        self.assertEqual(panel.toolbox.itemText(2), "Audio Output")


    def test_generation_help_tooltips_open_immediately_left_of_cursor(self):
        self.window = HarnessMainWindow(self.root)
        panel = self.window.workspace_view.settings.settings_panel
        value_control = panel.cfg_weight
        widget = panel.generation_form.labelForField(value_control)
        local_position = QPoint(2, 2)
        event = QHelpEvent(
            QEvent.Type.ToolTip,
            local_position,
            widget.mapToGlobal(local_position),
        )

        tooltip = panel._left_tooltip_filter.tooltip
        with patch.object(tooltip, "show_tip") as show:
            QApplication.sendEvent(widget, event)

        show.assert_called_once()
        text, position = show.call_args.args
        self.assertEqual(
            position.x(),
            event.globalPos().x()
            - panel._left_tooltip_filter.TOOLTIP_WIDTH
            - panel._left_tooltip_filter.CURSOR_GAP,
        )
        self.assertLess(position.x(), event.globalPos().x())
        self.assertEqual(
            position.y(),
            event.globalPos().y() + panel._left_tooltip_filter.VERTICAL_OFFSET,
        )
        self.assertEqual(text, widget.toolTip())

        value_event = QHelpEvent(
            QEvent.Type.ToolTip,
            local_position,
            value_control.mapToGlobal(local_position),
        )
        with patch.object(tooltip, "show_tip") as show:
            QApplication.sendEvent(value_control, value_event)
        show.assert_not_called()


    def test_generation_help_tooltip_moves_toward_pointer_gradually(self):
        self.window = HarnessMainWindow(self.root)
        tooltip = self.window.workspace_view.settings.settings_panel._left_tooltip_filter.tooltip
        start = QPoint(500, 200)
        target = QPoint(400, 260)
        tooltip.move(start)
        tooltip.follow(target)

        tooltip._advance_position()

        moved = tooltip.pos()
        self.assertGreater(moved.x(), target.x())
        self.assertLess(moved.x(), start.x())
        self.assertGreater(moved.y(), start.y())
        self.assertLess(moved.y(), target.y())


    def test_generation_help_tooltip_paints_its_card_background(self):
        self.window = HarnessMainWindow(self.root)
        tooltip = self.window.workspace_view.settings.settings_panel._left_tooltip_filter.tooltip
        tooltip.show_tip("<b>Guidance strength</b>", QPoint(100, 100))
        self.application.processEvents()

        image = tooltip.grab().toImage()
        background = image.pixelColor(5, image.height() // 2)

        self.assertEqual(background.name().upper(), MANTLE)
        self.assertEqual(background.alpha(), 255)
        tooltip.hide_tip()


    def test_splitting_mode_hides_irrelevant_controls(self):
        self.window = HarnessMainWindow(self.root)
        panel = self.window.workspace_view.settings.settings_panel

        def row_hidden(field):
            label = panel.splitting_form.labelForField(field)
            return field.isHidden() and label.isHidden()

        automatic_only = (
            panel.automatic_min_words,
            panel.automatic_max_words,
            panel.vram_safety_margin_mb,
            panel.adaptive_growth_interval,
        )

        self.assertTrue(row_hidden(panel.generation_max_words))
        for field in automatic_only:
            self.assertFalse(row_hidden(field))

        panel.splitting_mode.setCurrentText("manual")
        self.application.processEvents()

        self.assertFalse(row_hidden(panel.generation_max_words))
        for field in automatic_only:
            self.assertTrue(row_hidden(field))


    def test_model_selector_marks_installed_and_downloadable_models(self):
        hub = self.root / "models" / "huggingface" / "hub"
        snapshot = (
            hub
            / "models--ResembleAI--chatterbox"
            / "snapshots"
            / "revision"
        )
        snapshot.mkdir(parents=True)
        for filename in MODEL_DOWNLOAD_FILES["original"][1]:
            (snapshot / filename).write_bytes(b"cached")

        self.window = HarnessMainWindow(self.root)
        panel = self.window.workspace_view.settings.settings_panel
        labels = {
            str(panel.model.itemData(index)): panel.model.itemText(index)
            for index in range(panel.model.count())
        }

        self.assertEqual(
            labels,
            {
                "original": "Original",
                "turbo": "Turbo",
                "v3": "Multilingual V3",
                "nano": "Nano",
            },
        )
        for index in range(panel.model.count()):
            self.assertTrue(panel.model.itemIcon(index).isNull())

        self.assertEqual(panel.model_install_button.text(), "Installed")
        self.assertFalse(panel.model_install_button.isEnabled())
        self.assertEqual(
            panel.model_install_button.property("modelState"),
            "installed",
        )

        panel.model.setCurrentIndex(panel.model.findData("turbo"))

        self.assertEqual(panel.model_install_button.text(), "Install")
        self.assertTrue(panel.model_install_button.isEnabled())
        self.assertEqual(
            panel.model_install_button.property("modelState"),
            "install",
        )
        self.assertIn(
            "automatically",
            panel.model.itemData(
                panel.model.currentIndex(),
                Qt.ItemDataRole.ToolTipRole,
            ),
        )

        with (
            patch(
                "harness_ui.settings.models.AppDialog.confirm",
                return_value=True,
            ),
            patch.object(panel.model_controller.process, "start") as start,
        ):
            panel.model_install_button.click()

        start.assert_called_once()
        executable, arguments = start.call_args.args
        self.assertTrue(executable)
        self.assertEqual(arguments[:3], ("-m", "modules.model_download", "turbo"))
        self.assertEqual(
            arguments[arguments.index("--cache-root") + 1],
            str(self.root / "models" / "huggingface" / "hub"),
        )
        self.assertEqual(arguments[-2:], ("--operation", "install"))
        self.assertEqual(panel.model_install_button.text(), "Installing…")
        self.assertFalse(panel.model_install_button.isEnabled())


    def test_partial_model_snapshot_offers_repair(self):
        hub = self.root / "models" / "huggingface" / "hub"
        snapshot = (
            hub
            / "models--ResembleAI--chatterbox-nano"
            / "snapshots"
            / "revision"
        )
        snapshot.mkdir(parents=True)
        (snapshot / "vocab.json").write_bytes(b"partial")

        self.window = HarnessMainWindow(self.root)
        panel = self.window.workspace_view.settings.settings_panel
        panel.model.setCurrentIndex(panel.model.findData("nano"))

        self.assertEqual(panel.model_install_button.text(), "Repair")
        self.assertTrue(panel.model_install_button.isEnabled())
        self.assertEqual(
            panel.model_install_button.property("modelState"),
            "repair",
        )

        with (
            patch(
                "harness_ui.settings.models.AppDialog.confirm",
                return_value=True,
            ),
            patch.object(panel.model_controller.process, "start") as start,
        ):
            panel.model_install_button.click()

        _executable, arguments = start.call_args.args
        self.assertEqual(arguments[-2:], ("--operation", "repair"))
        self.assertEqual(panel.model_install_button.text(), "Repairing…")


    def test_model_install_button_recovers_when_process_cannot_start(self):
        self.window = HarnessMainWindow(self.root)
        panel = self.window.workspace_view.settings.settings_panel
        controller = panel.model_controller
        panel.model.setCurrentIndex(panel.model.findData("nano"))
        controller.installing_model_id = "nano"
        controller.installing_operation = "install"
        controller.refresh()
        self.assertEqual(panel.model_install_button.text(), "Installing…")

        with patch(
            "harness_ui.settings.models.AppDialog.critical"
        ) as critical:
            controller._process_error(QProcess.ProcessError.FailedToStart)

        self.assertIsNone(controller.installing_model_id)
        self.assertIsNone(controller.installing_operation)
        self.assertEqual(panel.model_install_button.text(), "Install")
        self.assertTrue(panel.model_install_button.isEnabled())
        critical.assert_called_once()


    def test_log_filter_can_be_changed_after_events_arrive(self):
        self.window = HarnessMainWindow(self.root)
        self.window.diagnostics_controller.append("normal diagnostic", "info")
        self.window.diagnostics_controller.append(
            "actionable failure",
            "error",
        )

        self.window.workspace_view.logs.log_filter.setCurrentText("Errors only")

        visible = self.window.workspace_view.logs.logs.toPlainText()
        self.assertNotIn("normal diagnostic", visible)
        self.assertIn("actionable failure", visible)


    def test_empty_states_offer_relevant_next_actions(self):
        self.window = HarnessMainWindow(self.root)

        self.assertFalse(self.window.workspace_view.jobs.refresh_jobs_button.icon().isNull())
        self.assertFalse(self.window.workspace_view.jobs.search_jobs_button.icon().isNull())
        self.assertFalse(self.window.workspace_view.jobs.new_job_button.icon().isNull())
        self.assertEqual(self.window.workspace_view.jobs.new_job_button.text(), "New job")
        self.assertFalse(hasattr(self.window, "job_search"))
        self.assertFalse(self.window.workspace_view.scripts.script_menu_button.icon().isNull())
        self.assertEqual(self.window.workspace_view.scripts.script_menu_button.text(), "")

        self.assertIs(
            self.window.workspace_view.queue.queue_stack.currentWidget(),
            self.window.workspace_view.queue.queue_empty_state,
        )
        self.assertEqual(
            self.window.workspace_view.queue.queue_empty_state.title_label.text(),
            "No active job",
        )
        self.assertIs(
            self.window.workspace_view.output.output_stack.currentWidget(),
            self.window.workspace_view.output.output_empty_state,
        )
        self.assertEqual(
            self.window.workspace_view.output.output_empty_state.title_label.text(),
            "No output yet",
        )
        self.assertIs(
            self.window.workspace_view.output.segment_stack.currentWidget(),
            self.window.workspace_view.output.segment_empty_state,
        )
        self.assertIs(
            self.window.workspace_view.logs.logs_stack.currentWidget(),
            self.window.workspace_view.logs.logs_empty_state,
        )
        self.assertEqual(
            self.window.workspace_view.logs.logs_empty_state.title_label.text(),
            "No diagnostics yet",
        )
        self.assertTrue(self.window.workspace_view.logs.logs_empty_state.action_button.isHidden())

        for state in (
            self.window.workspace_view.queue.queue_empty_state,
            self.window.workspace_view.output.output_empty_state,
            self.window.workspace_view.output.segment_empty_state,
            self.window.workspace_view.logs.logs_empty_state,
        ):
            self.assertEqual(state.icon_label.text(), "")
            self.assertIsNotNone(state.icon_label.pixmap())
            self.assertFalse(state.icon_label.pixmap().isNull())
        self.assertTrue(self.window.workspace_view.output.open_output_button.isHidden())
        self.assertTrue(self.window.workspace_view.output.open_output_folder_button.isHidden())
        self.assertTrue(self.window.workspace_view.output.play_segment_button.isHidden())
        self.assertTrue(self.window.workspace_view.logs.copy_logs_button.isHidden())
        self.assertTrue(self.window.workspace_view.logs.clear_logs_button.isHidden())
        self.assertTrue(
            all(button.isHidden() for button in self.window.workspace_view.queue.queue_action_buttons)
        )

        self.window.workspace_view.header.work_tabs.setCurrentIndex(2)
        self.window.workspace_view.output.output_empty_state.action_button.click()
        self.assertEqual(self.window.workspace_view.header.work_tabs.currentIndex(), 0)


    def test_empty_states_reject_legacy_text_icon_fallbacks(self):
        with self.assertRaisesRegex(TypeError, "bundled Lucide QIcons"):
            EmptyStateWidget(icon="!")


    def test_errors_filter_uses_a_no_errors_state(self):
        self.window = HarnessMainWindow(self.root)
        self.window.diagnostics_controller.append("ordinary activity", "info")
        self.assertIs(
            self.window.workspace_view.logs.logs_stack.currentWidget(),
            self.window.workspace_view.logs.logs,
        )

        self.window.workspace_view.logs.log_filter.setCurrentText("Errors only")

        self.assertIs(
            self.window.workspace_view.logs.logs_stack.currentWidget(),
            self.window.workspace_view.logs.logs_empty_state,
        )
        self.assertEqual(
            self.window.workspace_view.logs.logs_empty_state.title_label.text(),
            "No errors found",
        )
        self.assertEqual(self.window.workspace_view.logs.logs_empty_state.icon_label.text(), "")
        self.assertIsNotNone(self.window.workspace_view.logs.logs_empty_state.icon_label.pixmap())
        self.assertFalse(
            self.window.workspace_view.logs.logs_empty_state.icon_label.pixmap().isNull()
        )
        self.assertEqual(
            self.window.workspace_view.logs.logs_empty_state.action_button.text(),
            "Show all events",
        )

        self.window.workspace_view.logs.logs_empty_state.action_button.click()
        self.assertEqual(self.window.workspace_view.logs.log_filter.currentText(), "All events")
        self.assertIs(
            self.window.workspace_view.logs.logs_stack.currentWidget(),
            self.window.workspace_view.logs.logs,
        )


    def test_unpublished_completed_job_has_guided_states(self):
        self.window = HarnessMainWindow(self.root)
        manifest = self.window.service.create_job(JobRequest(
            scripts=(str(self.root / "input" / "script.txt"),),
        ))
        manifest["status"] = "complete"
        manifest["scripts"][0]["status"] = "complete"
        self.window.ui_state.set("current_job_id", manifest["job_id"])
        self.window.ui_state.set("current_manifest", manifest)

        self.window.job_presenter.render_manifest(manifest)

        self.assertEqual(
            self.window.workspace_view.header.completion_title.text(),
            "Generation finished",
        )
        self.assertFalse(self.window.workspace_view.header.completion_review_button.isEnabled())
        self.assertEqual(
            self.window.workspace_view.output.output_empty_state.title_label.text(),
            "Published output not found",
        )
        self.assertIs(
            self.window.workspace_view.output.output_stack.currentWidget(),
            self.window.workspace_view.output.output_empty_state,
        )
        self.assertEqual(
            self.window.workspace_view.output.segment_empty_state.title_label.text(),
            "Segments were cleaned up",
        )
        self.assertEqual(self.window.workspace_view.output.segment_empty_state.icon_label.text(), "")
        self.assertIsNotNone(
            self.window.workspace_view.output.segment_empty_state.icon_label.pixmap()
        )
        self.assertEqual(
            self.window.workspace_view.output.segment_empty_state.action_button.text(),
            "Open settings",
        )
        self.assertFalse(self.window.workspace_view.queue.restart_button.isHidden())
        self.assertTrue(self.window.workspace_view.queue.pause_button.isHidden())
        self.assertTrue(self.window.workspace_view.queue.cancel_button.isHidden())


    def test_major_sections_are_looser_than_related_action_groups(self):
        self.window = HarnessMainWindow(self.root)
        action_layouts = (
            self.window.workspace_view.scripts.editor_actions_layout,
            self.window.workspace_view.queue.queue_actions_layout,
            self.window.workspace_view.output.output_actions_layout,
            self.window.workspace_view.output.segment_actions_layout,
            self.window.workspace_view.logs.log_actions_layout,
        )

        self.assertGreaterEqual(self.window.workspace_view.workbench_layout.spacing(), 10)

        for action_layout in action_layouts:
            self.assertLess(
                action_layout.spacing(),
                self.window.workspace_view.workbench_layout.spacing(),
            )
            self.assertLessEqual(action_layout.spacing(), 6)


    def test_releasing_media_clears_the_windows_output_handle(self):
        self.window = HarnessMainWindow(self.root)
        output = self.root / "final" / "output.wav"
        output.parent.mkdir(exist_ok=True)
        output.write_bytes(b"placeholder")
        self.assertFalse(self.window.workspace_view.media_player.initialized)
        self.window.workspace_view.media_player.setSource(QUrl.fromLocalFile(str(output)))
        self.assertFalse(self.window.workspace_view.media_player.initialized)

        self.window.output_controller.release_media_source()

        self.assertTrue(self.window.workspace_view.media_player.source().isEmpty())
        self.assertFalse(self.window.workspace_view.output.play_button.isEnabled())


