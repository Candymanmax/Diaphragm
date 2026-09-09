"""Feature-specific desktop GUI tests."""

from tests.desktop_base import *
from types import SimpleNamespace
from PySide6.QtTest import QTest

class DesktopJobsTests(DesktopHarnessBase):
    def test_refresh_reuses_job_card_and_updates_its_content(self):
        self.window = HarnessMainWindow(self.root)
        manifest = self.window.service.create_job(JobRequest(
            scripts=(str(self.root / "input" / "script.txt"),),
        ))
        self.window.job_controller.refresh(select_job_id=manifest["job_id"])
        item = self.window.workspace_view.jobs.job_list.currentItem()
        card = self.window.workspace_view.jobs.job_list.itemWidget(item)

        manifest["name"] = "Updated job"
        manifest["status"] = "complete"
        manifest["scripts"][0]["chunks"] = [
            {"id": "segment-1", "status": "complete"},
        ]
        self.window.service.store.save(manifest)
        self.window.job_controller.refresh(select_job_id=manifest["job_id"])

        refreshed_item = self.window.workspace_view.jobs.job_list.currentItem()
        refreshed_card = self.window.workspace_view.jobs.job_list.itemWidget(
            refreshed_item
        )
        self.assertIs(refreshed_item, item)
        self.assertIs(refreshed_card, card)
        self.assertEqual(refreshed_card.title_label.text(), "Updated job")
        self.assertEqual(refreshed_card.status_chip.text(), "Complete")
        self.assertEqual(refreshed_card.progress_bar.value(), 1)

    def test_refresh_reuses_cards_when_job_order_changes(self):
        self.window = HarnessMainWindow(self.root)
        first = self.window.service.create_job(JobRequest(
            scripts=(str(self.root / "input" / "script.txt"),),
        ))
        second = self.window.service.create_job(JobRequest(
            scripts=(str(self.root / "input" / "script.txt"),),
        ))
        first["created_at"] = "2026-01-01T00:00:01+00:00"
        second["created_at"] = "2026-01-01T00:00:02+00:00"
        self.window.service.store.save(first)
        self.window.service.store.save(second)
        self.window.job_controller.refresh(select_job_id=second["job_id"])

        listing = self.window.workspace_view.jobs.job_list
        cards_before = {
            listing.item(index).data(Qt.ItemDataRole.UserRole): listing.itemWidget(
                listing.item(index)
            )
            for index in range(listing.count())
        }

        first["created_at"] = "2026-01-01T00:00:03+00:00"
        second["created_at"] = "2026-01-01T00:00:01+00:00"
        self.window.service.store.save(first)
        self.window.service.store.save(second)
        self.window.job_controller.refresh(select_job_id=first["job_id"])

        ordered_ids = [
            listing.item(index).data(Qt.ItemDataRole.UserRole)
            for index in range(listing.count())
        ]
        self.assertEqual(ordered_ids, [first["job_id"], second["job_id"]])
        for job_id, card in cards_before.items():
            item = next(
                listing.item(index)
                for index in range(listing.count())
                if listing.item(index).data(Qt.ItemDataRole.UserRole) == job_id
            )
            self.assertIs(listing.itemWidget(item), card)

    def test_idle_draft_hides_header_progress_panel(self):
        self.window = HarnessMainWindow(self.root)
        manifest = self.window.job_controller.create_temporary_job("Draft")
        self.window.job_controller.refresh(select_job_id=manifest["job_id"])
        self.window.show()
        self.application.processEvents()

        header = self.window.workspace_view.header
        self.assertFalse(header.progress_panel.isVisible())


    def test_job_sidebar_uses_compact_cards_and_hover_archive_action(self):
        self.window = HarnessMainWindow(self.root)
        manifest = self.window.service.create_job(JobRequest(
            scripts=(str(self.root / "input" / "script.txt"),),
        ))
        manifest["status"] = "running"
        manifest["scripts"][0]["status"] = "running"
        manifest["scripts"][0]["chunks"] = [
            {"id": "segment-1", "status": "complete"},
            {"id": "segment-2", "status": "pending"},
        ]
        self.window.service.store.save(manifest)
        self.window.ui_state.set("current_job_id", manifest["job_id"])
        self.window.job_controller.refresh(select_job_id=manifest["job_id"])
        self.window.show()
        self.application.processEvents()

        selected = self.window.workspace_view.jobs.job_list.currentItem()
        card = self.window.workspace_view.jobs.job_list.itemWidget(selected)
        self.assertIsInstance(card, JobCardWidget)
        self.assertEqual(selected.sizeHint().height(), 60)
        self.assertEqual(card.title_label.text(), "script")
        self.assertEqual(card.status_indicator.size().width(), 8)
        self.assertEqual(card.status_indicator.size().height(), 8)
        self.assertEqual(card.status_indicator.toolTip(), "Status: Running")
        self.assertEqual(card.status_chip.text(), "Running")
        self.assertEqual(card.status_chip.property("status"), "running")
        self.assertEqual(card.status_chip.toolTip(), "Status: Running")
        self.assertIn("Just now · 1/2 segments", card.meta_label.text())
        self.assertEqual(card.progress_bar.value(), 1)
        self.assertEqual(card.progress_bar.maximum(), 2)
        self.assertTrue(self.window.workspace_view.header.progress_panel.isVisible())
        self.assertTrue(card.property("selected"))
        self.assertEqual(
            self.window.workspace_view.jobs.search_jobs_button.geometry().top(),
            self.window.workspace_view.jobs.refresh_jobs_button.geometry().top(),
        )
        self.assertGreaterEqual(
            self.window.workspace_view.jobs.job_list.width(),
            210,
        )
        self.assertEqual(self.window.workspace_view.jobs.refresh_jobs_button.width(), 30)
        self.assertLess(
            self.window.workspace_view.jobs.refresh_jobs_button.geometry().top(),
            self.window.workspace_view.jobs.new_job_button.geometry().top(),
        )
        self.assertFalse(hasattr(self.window, "job_search"))
        self.assertFalse(card.archive_button.icon().isNull())
        self.assertTrue(card.archive_button.isVisible())
        self.assertEqual(card.archive_button.size(), QSize(24, 24))
        self.assertLessEqual(
            abs(
                card.archive_button.geometry().center().y()
                - card.rect().center().y()
            ),
            1,
        )
        self.assertFalse(card.archive_button.isEnabled())
        self.assertFalse(card.archive_button.property("hoverIconVisible"))
        self.assertFalse(card.archive_button.property("hoverHighlightVisible"))
        self.assertEqual(card.archive_button.toolTip(), "")
        self.assertEqual(selected.toolTip(), "")
        QTest.mouseClick(
            card,
            Qt.MouseButton.LeftButton,
            pos=QPoint(8, 8),
        )
        self.assertIs(
            self.window.workspace_view.jobs.job_list.currentItem(),
            selected,
        )


    def test_running_job_keeps_cancel_available_until_request_is_sent(self):
        self.window = HarnessMainWindow(self.root)
        manifest = self.window.service.create_job(JobRequest(
            scripts=(str(self.root / "input" / "script.txt"),),
        ))
        manifest["status"] = "running"
        manifest["scripts"][0]["status"] = "running"
        manifest["scripts"][0]["chunks"] = [
            {"id": "chunk0001", "status": "pending"},
        ]
        self.window.service.store.save(manifest)
        self.window.ui_state.set("current_job_id", manifest["job_id"])
        self.window.job_presenter.worker = SimpleNamespace(running=True)
        self.window.job_controller.refresh(select_job_id=manifest["job_id"])
        self.window.workspace_view.header.work_tabs.setCurrentIndex(1)
        self.window.show()
        self.application.processEvents()

        cancel = self.window.workspace_view.queue.cancel_button
        self.assertTrue(cancel.isVisible())
        self.assertTrue(cancel.isEnabled())
        self.assertEqual(cancel.text(), "Cancel")

        self.window.ui_state.set("cancel_requested", True)
        self.window.job_presenter.update_controls()

        self.assertTrue(cancel.isVisible())
        self.assertFalse(cancel.isEnabled())
        self.assertEqual(cancel.text(), "Cancelling…")


    def test_new_job_prompts_for_name_and_adds_temporary_job_card(self):
        self.window = HarnessMainWindow(self.root)

        with patch(
            "harness_ui.dialogs.NewJobDialog.prompt",
            return_value=("Narration draft", True),
        ):
            self.assertTrue(self.window.job_controller.new_job())

        self.assertEqual(self.window.workspace_view.jobs.job_list.count(), 1)
        item = self.window.workspace_view.jobs.job_list.item(0)
        card = self.window.workspace_view.jobs.job_list.itemWidget(item)
        self.assertIsInstance(card, JobCardWidget)
        self.assertEqual(card.title_label.text(), "Narration draft")
        self.assertEqual(card.status_indicator.toolTip(), "Status: Draft")
        self.assertEqual(card.status_chip.text(), "Draft")
        self.assertTrue(card.archive_button.isEnabled())
        self.assertEqual(self.window.workspace_view.header.job_title.text(), "Narration draft")
        current_manifest = self.window.ui_state.get("current_manifest")
        self.assertEqual(current_manifest["name"], "Narration draft")
        self.assertTrue(
            current_manifest["job_id"]
            in self.window.ui_state.get("temporary_jobs")
        )
        draft_folder = self.window.service.store.job_folder(
            current_manifest["job_id"]
        )
        self.assertTrue((draft_folder / "manifest.json").is_file())
        self.assertEqual(
            {path.name for path in draft_folder.iterdir()},
            {"manifest.json"},
        )


    def test_settings_follow_selected_job_and_drafts_keep_their_own_values(self):
        self.window = HarnessMainWindow(self.root)
        panel = self.window.workspace_view.settings.settings_panel
        saved_job = self.window.service.create_job(JobRequest(
            scripts=(str(self.root / "input" / "script.txt"),),
        ))
        saved_job["settings"]["model"] = "nano"
        self.window.service.store.save(saved_job)

        self.window.job_controller.refresh(select_job_id=saved_job["job_id"])

        self.assertEqual(panel.model.currentData(), "nano")
        self.assertFalse(panel.model.isEnabled())
        self.assertFalse(panel.splitting_mode.isEnabled())
        self.assertFalse(panel.chunk_size.isEnabled())
        self.assertIn("saved settings", panel.scope_hint.text())

        with patch(
            "harness_ui.dialogs.NewJobDialog.prompt",
            return_value=("Fresh draft", True),
        ):
            self.assertTrue(self.window.job_controller.new_job())

        draft_id = self.window.ui_state.get("current_job_id")
        self.assertTrue(panel.job_editable)
        self.assertEqual(panel.model.currentData(), "original")
        self.assertTrue(panel.splitting_mode.isEnabled())
        self.assertTrue(panel.chunk_size.isEnabled())

        panel.model.setCurrentIndex(panel.model.findData("nano"))
        self.application.processEvents()

        draft = self.window.service.load_job(draft_id)
        self.assertEqual(draft["settings"]["model"], "nano")
        self.assertEqual(self.window.service.load_config().model, "original")


    def test_new_job_prompt_is_frameless_and_validates_inline(self):
        self.window = HarnessMainWindow(self.root)
        dialog = NewJobDialog(self.window)

        self.assertTrue(
            dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
        )
        self.assertFalse(
            dialog.testAttribute(
                Qt.WidgetAttribute.WA_TranslucentBackground
            )
        )
        self.assertTrue(dialog.autoFillBackground())
        self.assertTrue(dialog.isModal())
        self.assertEqual(dialog.objectName(), "newJobDialog")
        self.assertEqual(dialog.windowTitle(), "New TTS job")
        self.assertEqual(
            dialog.findChild(QLabel, "newJobTitle").text(),
            "New TTS job",
        )
        self.assertIsNotNone(dialog.findChild(QLabel, "newJobIcon"))
        self.assertFalse(dialog.create_button.property("ghost"))
        self.assertTrue(dialog.create_button.property("primary"))
        self.assertIsNotNone(
            dialog.findChild(QFrame, "newJobPanel")
        )

        dialog.name_input.clear()
        dialog._submit()
        self.assertFalse(dialog.validation.isHidden())
        self.assertNotEqual(dialog.result(), QDialog.DialogCode.Accepted)

        dialog.name_input.setText("  Voiceover draft  ")
        dialog._submit()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.job_name(), "Voiceover draft")


    def test_job_view_buttons_show_active_or_archived_jobs(self):
        self.window = HarnessMainWindow(self.root)
        manifest = self.window.service.create_job(JobRequest(
            scripts=(str(self.root / "input" / "script.txt"),),
        ))
        self.window.service.set_archived(manifest["job_id"], True)
        self.window.job_controller.refresh()

        self.assertFalse(hasattr(self.window, "show_archived"))
        self.assertFalse(hasattr(self.window, "job_filter"))
        self.assertEqual(self.window.workspace_view.jobs.jobs_button.text(), "Jobs")
        self.assertEqual(
            self.window.workspace_view.jobs.archived_jobs_button.text(),
            "Archived",
        )
        self.assertFalse(self.window.workspace_view.jobs.jobs_button.isCheckable())
        self.assertFalse(self.window.workspace_view.jobs.archived_jobs_button.isCheckable())
        self.assertFalse(self.window.workspace_view.jobs.jobs_button.icon().isNull())
        self.assertFalse(self.window.workspace_view.jobs.archived_jobs_button.icon().isNull())
        self.assertEqual(self.window.workspace_view.jobs.job_list.count(), 0)
        self.assertIs(
            self.window.workspace_view.jobs.job_list_stack.currentWidget(),
            self.window.workspace_view.jobs.jobs_empty_state,
        )
        self.assertEqual(
            self.window.workspace_view.jobs.jobs_empty_state.title_label.text(),
            "No jobs yet",
        )

        self.window.workspace_view.jobs.archived_jobs_button.click()
        self.application.processEvents()

        self.assertEqual(self.window.workspace_view.jobs.job_list.count(), 1)
        card = self.window.workspace_view.jobs.job_list.itemWidget(self.window.workspace_view.jobs.job_list.item(0))
        self.assertIn("Archived", card.meta_label.text())

        self.window.workspace_view.jobs.jobs_button.click()
        self.application.processEvents()
        self.assertEqual(self.window.workspace_view.jobs.job_list.count(), 0)
        self.assertEqual(
            self.window.workspace_view.jobs.jobs_empty_state.title_label.text(),
            "No jobs yet",
        )


    def test_startup_opens_the_topmost_active_job(self):
        self.window = HarnessMainWindow(self.root)
        older = self.window.service.create_job(JobRequest(
            scripts=(str(self.root / "input" / "script.txt"),),
            name="Older job",
        ))
        newer = self.window.service.create_job(JobRequest(
            scripts=(str(self.root / "input" / "script.txt"),),
            name="Newer job",
        ))
        older["created_at"] = "2020-01-01T00:00:00+00:00"
        newer["created_at"] = "2021-01-01T00:00:00+00:00"
        self.window.service.store.save(older)
        self.window.service.store.save(newer)
        self.window.job_controller.refresh()

        with patch(
            "harness_ui.dialogs.NewJobDialog.prompt"
        ) as prompt:
            self.window.job_controller.initialize_startup_job()

        prompt.assert_not_called()
        self.assertEqual(
            self.window.ui_state.get("current_job_id"),
            newer["job_id"],
        )
        self.assertEqual(self.window.workspace_view.header.job_title.text(), "Newer job")


    def test_startup_opens_a_blank_workbench_when_active_list_is_empty(self):
        self.window = HarnessMainWindow(self.root)
        archived = self.window.service.create_job(JobRequest(
            scripts=(str(self.root / "input" / "script.txt"),),
            name="Archived job",
        ))
        self.window.service.set_archived(archived["job_id"], True)

        with patch(
            "harness_ui.dialogs.NewJobDialog.prompt",
        ) as prompt:
            self.window.job_controller.initialize_startup_job()

        prompt.assert_not_called()
        self.assertIsNone(self.window.ui_state.get("current_job_id"))
        self.assertIsNone(self.window.ui_state.get("current_manifest"))
        self.assertEqual(self.window.workspace_view.header.job_title.text(), "New TTS job")
        self.assertEqual(self.window.workspace_view.header.job_segment_count.text(), "No segments")


    def test_existing_named_jobs_keep_their_name(self):
        self.window = HarnessMainWindow(self.root)
        manifest = self.window.service.create_job(JobRequest(
            scripts=(str(self.root / "input" / "script.txt"),),
            name="Saved narration",
        ))
        self.window.job_controller.refresh(select_job_id=manifest["job_id"])

        card = self.window.workspace_view.jobs.job_list.itemWidget(
            self.window.workspace_view.jobs.job_list.currentItem()
        )
        self.assertEqual(card.title_label.text(), "Saved narration")
        self.assertEqual(self.window.workspace_view.header.job_title.text(), "Saved narration")


    def test_search_opens_a_job_prompt_with_filtered_results(self):
        self.window = HarnessMainWindow(self.root)
        manifest = self.window.service.create_job(JobRequest(
            scripts=(str(self.root / "input" / "script.txt"),),
            name="Searchable narration",
        ))

        dialog = self.window.search_controller.create_job_dialog()
        self.assertEqual(dialog.objectName(), "jobSearchDialog")
        self.assertIsNotNone(dialog.findChild(QFrame, "jobSearchPanel"))
        self.assertEqual(dialog.search_input.placeholderText(), "Search jobs")
        self.assertIn(
            "QFrame#jobSearchPanel {\n    background: #24273A;",
            self.application.styleSheet(),
        )
        self.assertIn(
            "QLineEdit#jobSearchInput {\n    background: #24273A;",
            self.application.styleSheet(),
        )
        self.assertIn(
            "QListWidget#jobSearchResults {\n    background: #24273A;",
            self.application.styleSheet(),
        )
        self.assertEqual(dialog.results.count(), 1)
        self.assertIn(
            "QListWidget#jobSearchResults::item:hover",
            self.application.styleSheet(),
        )

        dialog.search_input.setText("script")
        self.application.processEvents()
        self.assertEqual(dialog.results.item(0).text(), "No matching jobs")

        dialog.search_input.setText("searchable")
        self.application.processEvents()
        item = dialog.results.item(0)
        self.assertEqual(item.text(), "")
        self.assertFalse(item.isSelected())
        self.assertIn(
            "Searchable narration",
            item.data(Qt.ItemDataRole.AccessibleTextRole),
        )
        self.assertEqual(
            item.data(Qt.ItemDataRole.UserRole),
            manifest["job_id"],
        )

        self.window.search_controller.open_job_result(dialog, item)
        self.assertEqual(
            self.window.ui_state.get("current_job_id"),
            manifest["job_id"],
        )
        dialog.close()


    def test_archive_action_loads_the_selected_card_before_archiving(self):
        self.window = HarnessMainWindow(self.root)
        manifest = self.window.service.create_job(JobRequest(
            scripts=(str(self.root / "input" / "script.txt"),),
        ))
        manifest["status"] = "complete"
        manifest["scripts"][0]["status"] = "complete"
        self.window.service.store.save(manifest)

        self.window.ui_state.set("current_job_id", manifest["job_id"])
        self.window.ui_state.set("current_manifest", None)
        self.window.job_controller.refresh(select_job_id=manifest["job_id"])

        self.assertIsNotNone(self.window.ui_state.get("current_manifest"))
        card = self.window.workspace_view.jobs.job_list.itemWidget(
            self.window.workspace_view.jobs.job_list.currentItem()
        )
        self.assertTrue(card.archive_button.isEnabled())
        self.window.show()
        self.application.processEvents()
        QTest.mouseMove(card, QPoint(8, 8))
        self.application.processEvents()
        self.assertTrue(card.archive_button.property("hoverIconVisible"))
        self.assertFalse(card.archive_button.property("hoverHighlightVisible"))

        # A refresh while the cursor is over the card, but not the action,
        # must not turn the action's highlight on.
        self.window.job_controller.refresh(select_job_id=manifest["job_id"])
        self.application.processEvents()
        refreshed_card = self.window.workspace_view.jobs.job_list.itemWidget(
            self.window.workspace_view.jobs.job_list.currentItem()
        )
        self.assertTrue(refreshed_card.archive_button.property("hoverIconVisible"))
        self.assertFalse(
            refreshed_card.archive_button.property("hoverHighlightVisible")
        )

        QTest.mouseMove(
            refreshed_card.archive_button,
            refreshed_card.archive_button.rect().center(),
        )
        self.application.processEvents()
        self.assertTrue(refreshed_card.archive_button.property("hoverHighlightVisible"))

        # The normal poll refresh replaces sidebar cards once per second. The
        # action should remain visible when the cursor never leaves its area.
        self.window.job_controller.refresh(select_job_id=manifest["job_id"])
        self.application.processEvents()
        refreshed_card = self.window.workspace_view.jobs.job_list.itemWidget(
            self.window.workspace_view.jobs.job_list.currentItem()
        )
        self.assertTrue(refreshed_card.archive_button.property("hoverIconVisible"))
        self.assertTrue(
            refreshed_card.archive_button.property("hoverHighlightVisible")
        )
        self.assertFalse(refreshed_card.archive_button.icon().isNull())

        self.window.job_controller.toggle_archive(manifest["job_id"])

        archived = self.window.service.load_job(manifest["job_id"])
        self.assertTrue(archived["archived"])
        self.assertIsNone(self.window.ui_state.get("current_job_id"))
        self.assertEqual(self.window.workspace_view.jobs.job_list.count(), 0)
        self.assertEqual(self.window.statusBar().currentMessage(), "Archived job")


    def test_job_context_menu_exposes_safe_contextual_actions(self):
        self.window = HarnessMainWindow(self.root)
        manifest = self.window.service.create_job(JobRequest(
            scripts=(str(self.root / "input" / "script.txt"),),
        ))
        self.window.job_controller.refresh(select_job_id=manifest["job_id"])
        menu = self.window.job_controller.build_context_menu(manifest)
        actions = {
            action.objectName(): action
            for action in menu.actions()
            if action.objectName()
        }

        self.assertEqual(
            list(actions),
            [
                "jobContextProgress",
                "jobContextReview",
                "jobContextOutputFolder",
                "jobContextArchive",
                "jobContextDelete",
            ],
        )
        self.assertEqual(actions["jobContextArchive"].text(), "Archive job")
        self.assertTrue(actions["jobContextDelete"].isEnabled())
        self.assertTrue(actions["jobContextReview"].isEnabled())
        self.assertTrue(actions["jobContextOutputFolder"].isEnabled())

        manifest["status"] = "running"
        active_menu = self.window.job_controller.build_context_menu(manifest)
        active_actions = {
            action.objectName(): action
            for action in active_menu.actions()
            if action.objectName()
        }
        self.assertFalse(active_actions["jobContextArchive"].isEnabled())
        self.assertFalse(active_actions["jobContextDelete"].isEnabled())


    def test_temporary_job_context_menu_uses_discard_and_hides_output_folder(self):
        self.window = HarnessMainWindow(self.root)
        manifest = self.window.job_controller.create_temporary_job("Draft")
        self.window.job_controller.refresh(select_job_id=manifest["job_id"])
        menu = self.window.job_controller.build_context_menu(manifest)
        actions = {
            action.objectName(): action
            for action in menu.actions()
            if action.objectName()
        }

        self.assertIn("jobContextReview", actions)
        self.assertNotIn("jobContextOutputFolder", actions)
        self.assertEqual(actions["jobContextArchive"].text(), "Archive job")
        self.assertTrue(actions["jobContextArchive"].isEnabled())

        actions["jobContextArchive"].trigger()

        self.assertTrue(
            self.window.ui_state.get("temporary_jobs")[manifest["job_id"]][
                "archived"
            ]
        )
        self.assertTrue(
            self.window.service.load_job(manifest["job_id"])["archived"]
        )
        self.assertEqual(self.window.workspace_view.jobs.job_list.count(), 0)

        self.window.workspace_view.jobs.archived_jobs_button.click()
        self.application.processEvents()
        self.assertEqual(self.window.workspace_view.jobs.job_list.count(), 1)

        self.assertEqual(
            self.window.workspace_view.jobs.job_list.item(0).data(
                Qt.ItemDataRole.UserRole
            ),
            manifest["job_id"],
        )


    def test_running_a_draft_promotes_it_and_removes_its_manifest(self):
        self.window = HarnessMainWindow(self.root)
        draft = self.window.job_controller.create_temporary_job("Run me")
        draft_id = draft["job_id"]
        draft_folder = self.window.service.store.job_folder(draft_id)
        self.window.job_controller.reset_view(draft)
        self.window.job_controller.refresh(select_job_id=draft_id)

        config = type("Config", (), {"voice": "voice.wav"})()
        persistent = {"job_id": "persistent-job"}
        generation = self.window.generation_controller

        with (
            patch.object(
                self.window.script_controller,
                "checked_paths_for_run",
                return_value=(self.root / "input" / "script.txt",),
            ),
            patch.object(
                generation.settings_panel,
                "current_config",
                return_value=config,
            ),
            patch.object(
                generation.settings_panel,
                "summary",
                return_value="",
            ),
            patch.object(
                self.window.service,
                "resolve_voice",
                return_value=self.root / "voices" / "voice.wav",
            ),
            patch.object(
                self.window.service,
                "create_job",
                return_value=persistent,
            ) as create_job,
            patch.object(generation, "_refresh_jobs"),
            patch.object(generation, "start") as start,
            patch(
                "harness_ui.controllers.generation.commands.AppDialog.confirm",
                return_value=True,
            ),
        ):
            generation.run_new_job()

        self.assertFalse(draft_folder.exists())
        self.assertNotIn(draft_id, self.window.ui_state.get("temporary_jobs"))
        self.assertEqual(create_job.call_args.args[0].name, "Run me")
        start.assert_called_once_with("prepared")


    def test_draft_job_is_visible_after_reopening_the_window(self):
        self.window = HarnessMainWindow(self.root)
        manifest = self.window.job_controller.create_temporary_job(
            "Durable draft"
        )
        draft_id = manifest["job_id"]

        self.window.close()
        self.application.processEvents()
        self.window = HarnessMainWindow(self.root)

        item_ids = [
            self.window.workspace_view.jobs.job_list.item(index).data(
                Qt.ItemDataRole.UserRole
            )
            for index in range(self.window.workspace_view.jobs.job_list.count())
        ]
        self.assertIn(draft_id, item_ids)
        self.assertEqual(
            self.window.service.load_job(draft_id)["name"],
            "Durable draft",
        )


    def test_context_actions_keep_target_job_and_open_empty_review(self):
        self.window = HarnessMainWindow(self.root)
        manifest = self.window.service.create_job(JobRequest(
            scripts=(str(self.root / "input" / "script.txt"),),
        ))
        self.window.job_controller.refresh(select_job_id=manifest["job_id"])
        menu = self.window.job_controller.build_context_menu(manifest)
        actions = {
            action.objectName(): action
            for action in menu.actions()
            if action.objectName()
        }
        requested_tabs = []
        self.window.job_controller.tabRequested.connect(requested_tabs.append)

        actions["jobContextReview"].trigger()

        self.assertEqual(requested_tabs, [2])
        self.assertEqual(
            self.window.ui_state.get("current_job_id"),
            manifest["job_id"],
        )
        self.assertIs(
            self.window.workspace_view.output.output_stack.currentWidget(),
            self.window.workspace_view.output.output_empty_state,
        )


    def test_context_job_deletion_recycles_data_but_keeps_output(self):
        self.window = HarnessMainWindow(self.root)
        manifest = self.window.service.create_job(JobRequest(
            scripts=(str(self.root / "input" / "script.txt"),),
        ))
        job_folder = self.window.service.store.job_folder(manifest["job_id"])
        output = self.root / manifest["scripts"][0]["published_output"]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"published audio")
        self.window.job_controller.refresh(select_job_id=manifest["job_id"])
        menu = self.window.job_controller.build_context_menu(manifest)
        delete_action = next(
            action
            for action in menu.actions()
            if action.objectName() == "jobContextDelete"
        )

        def fake_trash(path):
            shutil.rmtree(path)
            return True

        with (
            patch(
                "harness_ui.controllers.jobs.lifecycle.AppDialog.confirm",
                return_value=True,
            ),
            patch.object(
                self.window.job_controller,
                "_move_to_trash",
                side_effect=fake_trash,
            ),
        ):
            delete_action.trigger()

        self.assertFalse(job_folder.exists())
        self.assertTrue(output.exists())
        self.assertEqual(self.window.workspace_view.jobs.job_list.count(), 0)
        self.assertIsNone(self.window.ui_state.get("current_job_id"))
        self.assertIn(
            "output files kept",
            self.window.statusBar().currentMessage(),
        )


    def test_completed_job_header_replaces_progress_with_output_summary(self):
        self.window = HarnessMainWindow(self.root)
        manifest = self.window.service.create_job(JobRequest(
            scripts=(str(self.root / "input" / "script.txt"),),
        ))
        manifest["status"] = "complete"
        manifest["scripts"][0]["status"] = "complete"
        manifest["scripts"][0]["chunks"] = [
            {"id": "segment-1", "status": "complete"},
            {"id": "segment-2", "status": "complete"},
        ]
        output = self.root / manifest["scripts"][0]["published_output"]
        output.parent.mkdir(parents=True, exist_ok=True)

        with wave.open(str(output), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(24000)
            audio.writeframes(b"\0\0" * 240)

        self.window.ui_state.set("current_job_id", manifest["job_id"])
        self.window.ui_state.set("current_manifest", manifest)
        self.window.job_presenter.render_manifest(manifest)
        self.window.show()
        self.application.processEvents()

        self.assertEqual(self.window.workspace_view.header.job_title.text(), "script")
        self.assertEqual(
            self.window.workspace_view.header.job_segment_count.text(),
            "2/2 segments",
        )
        self.assertFalse(self.window.workspace_view.header.progress_panel.isVisible())
        self.assertTrue(self.window.workspace_view.header.completion_panel.isVisible())
        self.assertEqual(
            self.window.workspace_view.header.completion_text.text(),
            "2 segments generated · output ready",
        )
        self.assertEqual(
            self.window.workspace_view.header.completion_title.text(),
            "Generation complete",
        )
        self.assertEqual(self.window.workspace_view.header.completion_mark.text(), "")
        self.assertIsNotNone(self.window.workspace_view.header.completion_mark.pixmap())
        self.assertFalse(self.window.workspace_view.header.completion_mark.pixmap().isNull())
        self.assertTrue(self.window.workspace_view.header.completion_review_button.isEnabled())
        self.assertTrue(self.window.workspace_view.header.completion_new_job_button.isEnabled())
        self.assertIs(
            self.window.workspace_view.output.output_stack.currentWidget(),
            self.window.workspace_view.output.output_content,
        )
        self.assertFalse(self.window.workspace_view.output.open_output_button.isHidden())
        self.assertFalse(self.window.workspace_view.output.open_output_folder_button.isHidden())
        self.assertTrue(self.window.workspace_view.output.play_segment_button.isHidden())
        self.assertEqual(self.window.workspace_view.header.job_header_action.text(), "Open output")
        self.assertTrue(self.window.workspace_view.header.job_header_action.isEnabled())

        self.window.workspace_view.header.work_tabs.setCurrentIndex(0)
        self.window.workspace_view.header.completion_review_button.click()
        self.assertEqual(self.window.workspace_view.header.work_tabs.currentIndex(), 2)

        with patch(
            "harness_ui.controllers.output_review.QDesktopServices.openUrl"
        ) as open_url:
            self.window.workspace_view.header.job_header_action.click()
            open_url.assert_called_once()


    def test_relative_job_times_are_compact(self):
        now = datetime(2026, 8, 12, 16, 0, tzinfo=timezone.utc)
        self.assertEqual(relative_time(now.isoformat(), now), "Just now")
        self.assertEqual(
            relative_time((now - timedelta(minutes=4)).isoformat(), now),
            "4m ago",
        )
        self.assertEqual(
            relative_time((now - timedelta(hours=3)).isoformat(), now),
            "3h ago",
        )


