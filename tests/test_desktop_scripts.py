"""Feature-specific desktop GUI tests."""

from tests.desktop_base import *
from PySide6.QtTest import QTest

class DesktopScriptsTests(DesktopHarnessBase):
    def test_empty_editor_actions_create_or_browse_scripts(self):
        (self.root / "input" / "script.txt").unlink()
        source = self.root / "source.txt"
        source.write_text("Browse this script.", encoding="utf-8")
        self.window = HarnessMainWindow(self.root)
        scripts = self.window.workspace_view.scripts
        empty_state = scripts.editor_empty_state

        self.assertEqual(scripts.script_list.count(), 0)
        empty_state.action_button.click()
        self.assertEqual(scripts.script_list.count(), 1)
        self.assertIs(scripts.editor_stack.currentWidget(), scripts.editor_content)

        self.window.script_controller.remove_current()
        self.assertIs(scripts.editor_stack.currentWidget(), empty_state)

        with patch(
            "harness_ui.controllers.script_documents.QFileDialog.getOpenFileNames",
            return_value=([str(source)], "Text scripts (*.txt)"),
        ) as dialog:
            empty_state.secondary_action_button.click()

        dialog.assert_called_once()
        self.assertEqual(scripts.script_list.count(), 1)
        self.assertIs(scripts.editor_stack.currentWidget(), scripts.editor_content)


    def test_script_row_delete_button_discards_an_in_memory_script(self):
        self.window = HarnessMainWindow(self.root)
        scripts = self.window.workspace_view.scripts
        self.assertTrue(self.window.script_controller.new_document())
        item = scripts.script_list.currentItem()
        self.assertIsNotNone(item)

        self.window.show()
        self.application.processEvents()
        delete_button = scripts.script_list.delete_button
        self.assertFalse(delete_button.isVisible())

        item_rect = scripts.script_list.visualItemRect(item)
        QTest.mouseMove(
            scripts.script_list.viewport(),
            QPoint(item_rect.left() + 12, item_rect.center().y()),
        )
        self.application.processEvents()
        self.assertTrue(delete_button.isVisible())
        self.assertEqual(delete_button.objectName(), "scriptRowDeleteButton")
        self.assertEqual(delete_button.accessibleName(), "Delete script")
        self.assertEqual(delete_button.size(), QSize(24, 24))

        QTest.mouseMove(delete_button, delete_button.rect().center())
        self.application.processEvents()
        delete_button.click()
        self.application.processEvents()

        self.assertEqual(scripts.script_list.count(), 1)
        self.assertEqual(
            self.window.script_controller.current_path,
            self.root / "input" / "script.txt",
        )


    def test_switching_scripts_saves_the_previous_editor_immediately(self):
        second = self.root / "input" / "second.txt"
        second.write_text("Second script.", encoding="utf-8")
        first = self.root / "input" / "script.txt"
        self.window = HarnessMainWindow(self.root)
        self.window.script_controller.add_paths((second,))
        self.window.workspace_view.scripts.script_editor.setPlainText("Updated first script.")

        second_item = next(
            self.window.workspace_view.scripts.script_list.item(index)
            for index in range(self.window.workspace_view.scripts.script_list.count())
            if Path(
                self.window.workspace_view.scripts.script_list.item(index).data(
                    Qt.ItemDataRole.UserRole
                )
            ) == second
        )
        self.window.workspace_view.scripts.script_list.setCurrentItem(second_item)

        self.assertEqual(
            first.read_text(encoding="utf-8"),
            "Updated first script.",
        )
        self.assertEqual(self.window.script_controller.current_path, second)


    def test_job_snapshot_uses_latest_editor_text(self):
        self.window = HarnessMainWindow(self.root)
        self.window.workspace_view.scripts.script_editor.setPlainText("Latest editor version.")
        self.assertTrue(self.window.script_controller.save())
        script = self.window.script_controller.checked_paths()[0]

        manifest = self.window.service.create_job(JobRequest(
            scripts=(str(script),),
        ))
        copied = self.window.service.store.resolve_artifact(
            manifest["job_id"],
            manifest["scripts"][0]["source_path"],
        )

        self.assertEqual(
            copied.read_text(encoding="utf-8"),
            "Latest editor version.",
        )


    def test_save_as_creates_and_selects_the_new_file(self):
        self.window = HarnessMainWindow(self.root)
        original = self.root / "input" / "script.txt"
        duplicate = self.root / "input" / "saved-copy.txt"
        self.window.workspace_view.scripts.script_editor.setPlainText("Saved as a new file.")

        with patch(
            "harness_ui.controllers.script_documents.QFileDialog.getSaveFileName",
            return_value=(str(duplicate), "Text scripts (*.txt)"),
        ):
            result = self.window.script_controller.save_as()

        self.assertTrue(result)
        self.assertEqual(
            duplicate.read_text(encoding="utf-8"),
            "Saved as a new file.",
        )
        self.assertEqual(
            original.read_text(encoding="utf-8"),
            "A desktop harness test.",
        )
        self.assertEqual(self.window.script_controller.current_path, duplicate)
        self.assertEqual(self.window.workspace_view.scripts.script_list.count(), 2)


    def test_dropped_script_becomes_an_unsaved_memory_script(self):
        self.window = HarnessMainWindow(self.root)
        original = self.root / "input" / "script.txt"
        original_text = original.read_text(encoding="utf-8")

        self.window.script_controller.add_dropped_paths((original,))

        self.assertTrue(original.exists())
        self.assertEqual(original.read_text(encoding="utf-8"), original_text)
        dropped_item = next(
            item
            for index in range(
                self.window.workspace_view.scripts.script_list.count()
            )
            if (
                item := self.window.workspace_view.scripts.script_list.item(index)
            )
            and self.window.script_controller.path_for_item(item) is None
        )
        self.assertIsNone(
            dropped_item.data(Qt.ItemDataRole.UserRole)
        )
        self.assertEqual(
            dropped_item.data(SCRIPT_TEXT_ROLE),
            original_text,
        )

        self.window.workspace_view.scripts.script_list.setCurrentItem(
            dropped_item
        )
        self.window.script_controller.remove_current()
        self.assertTrue(original.exists())
        self.assertEqual(original.read_text(encoding="utf-8"), original_text)


    def test_new_script_stays_in_memory_until_save_prompts_for_filename(self):
        self.window = HarnessMainWindow(self.root)
        new_path = self.root / "input" / "draft.txt"

        self.assertTrue(self.window.script_controller.new_document())
        item = self.window.workspace_view.scripts.script_list.currentItem()

        self.assertIsNone(item.data(Qt.ItemDataRole.UserRole))
        self.assertFalse(new_path.exists())
        self.assertEqual(self.window.workspace_view.scripts.editor_path.text(), "Untitled script")

        self.window.workspace_view.scripts.script_editor.setPlainText("An unsaved draft.")
        self.assertFalse(new_path.exists())

        with patch(
            "harness_ui.controllers.script_documents.QFileDialog.getSaveFileName",
            return_value=(str(new_path), "Text scripts (*.txt)"),
        ) as dialog:
            self.assertTrue(self.window.script_controller.save())

        dialog.assert_called_once()
        self.assertEqual(
            new_path.read_text(encoding="utf-8"),
            "An unsaved draft.",
        )
        self.assertEqual(self.window.script_controller.current_path, new_path)
        self.assertEqual(self.window.workspace_view.scripts.editor_path.text(), "input/draft.txt")
        self.assertEqual(self.window.workspace_view.scripts.script_save_state.text(), "Saved")
        self.assertEqual(item.toolTip(), "")


    def test_first_unsaved_script_enables_the_editor_in_an_empty_library(self):
        (self.root / "input" / "script.txt").unlink()
        self.window = HarnessMainWindow(self.root)

        self.assertEqual(self.window.workspace_view.scripts.script_list.count(), 0)
        scripts = self.window.workspace_view.scripts
        self.assertIs(scripts.editor_stack.currentWidget(), scripts.editor_empty_state)
        self.assertFalse(self.window.workspace_view.scripts.script_editor.isEnabled())
        self.assertTrue(self.window.script_controller.new_document())

        item = self.window.workspace_view.scripts.script_list.currentItem()
        self.assertIsNotNone(item)
        self.assertIsNone(self.window.script_controller.path_for_item(item))
        self.assertIs(scripts.editor_stack.currentWidget(), scripts.editor_content)
        self.assertTrue(self.window.workspace_view.scripts.script_editor.isEnabled())
        self.assertFalse(self.window.workspace_view.scripts.script_editor.isReadOnly())
        self.assertTrue(self.window.workspace_view.scripts.save_as_button.isEnabled())

        self.window.workspace_view.scripts.script_editor.insertPlainText("Editable unsaved draft.")
        self.assertEqual(
            item.data(SCRIPT_TEXT_ROLE),
            "Editable unsaved draft.",
        )
        self.window.script_controller.remove_row(
            self.window.workspace_view.scripts.script_list.currentRow()
        )
        self.assertIs(scripts.editor_stack.currentWidget(), scripts.editor_empty_state)


    def test_switching_scripts_keeps_unsaved_draft_without_prompting(self):
        self.window = HarnessMainWindow(self.root)
        self.assertTrue(self.window.script_controller.new_document())
        draft = self.window.workspace_view.scripts.script_list.currentItem()
        self.window.workspace_view.scripts.script_editor.setPlainText("Keep this draft in memory.")
        existing = self.window.workspace_view.scripts.script_list.item(0)

        with patch(
            "harness_ui.controllers.script_documents.QFileDialog.getSaveFileName",
        ) as dialog:
            self.window.workspace_view.scripts.script_list.setCurrentItem(existing)
            self.window.workspace_view.scripts.script_list.setCurrentItem(draft)

        dialog.assert_not_called()
        self.assertEqual(
            self.window.workspace_view.scripts.script_editor.toPlainText(),
            "Keep this draft in memory.",
        )
        self.assertIsNone(draft.data(Qt.ItemDataRole.UserRole))
        self.window.script_controller.delete_current()


    def test_exiting_unsaved_script_skips_save_as_and_uses_exit_confirmation(self):
        self.window = HarnessMainWindow(self.root)
        self.assertTrue(self.window.script_controller.new_document())

        with (
            patch.object(
                self.window.shutdown_controller,
                "confirm_unsaved_exit",
                return_value=True,
            ) as confirm,
            patch(
             "harness_ui.controllers.script_documents.QFileDialog.getSaveFileName",
             ) as save_dialog,
         ):
            self.assertTrue(self.window.close())

        confirm.assert_called_once_with()
        save_dialog.assert_not_called()
        self.window.script_controller.remove_row(
            self.window.workspace_view.scripts.script_list.currentRow()
        )


    def test_unsaved_exit_dialog_is_frameless_and_has_exit_actions(self):
        self.window = HarnessMainWindow(self.root)
        state = {}

        def choose_go_back():
            dialog = self.window.findChild(
                QDialog,
                "unsavedScriptDialog",
            )
            state["found"] = dialog is not None

            if dialog is None:
                return

            state["frameless"] = bool(
                dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
            )
            state["has_title_hint"] = bool(
                dialog.windowFlags() & Qt.WindowType.WindowTitleHint
            )
            state["buttons"] = [
                button.text()
                for button in dialog.findChildren(QPushButton)
            ]
            dialog.findChild(
                QPushButton,
                "unsavedScriptGoBack",
            ).click()

        QTimer.singleShot(0, choose_go_back)
        self.assertFalse(UnsavedScriptDialog.confirm(self.window))
        self.assertTrue(state["found"])
        self.assertTrue(state["frameless"])
        self.assertFalse(state["has_title_hint"])
        self.assertEqual(state["buttons"], ["Go back", "Exit"])


    def test_remove_from_list_saves_but_does_not_delete(self):
        second = self.root / "input" / "second.txt"
        second.write_text("Second script.", encoding="utf-8")
        first = self.root / "input" / "script.txt"
        self.window = HarnessMainWindow(self.root)
        self.window.script_controller.add_paths((second,))
        self.window.workspace_view.scripts.script_editor.setPlainText("Keep this update.")

        self.window.script_controller.remove_current()

        self.assertTrue(first.exists())
        self.assertEqual(first.read_text(encoding="utf-8"), "Keep this update.")
        self.assertEqual(self.window.workspace_view.scripts.script_list.count(), 1)
        self.assertEqual(self.window.script_controller.current_path, second)
        self.assertEqual(
            self.window.workspace_view.scripts.script_editor.toPlainText(),
            "Second script.",
        )


    def test_remove_from_list_discards_temporary_script_without_saving(self):
        original = self.root / "input" / "script.txt"
        self.window = HarnessMainWindow(self.root)
        self.assertTrue(self.window.script_controller.new_document())
        self.window.workspace_view.scripts.script_editor.setPlainText("Temporary words.")
        menu = self.window.script_controller.build_context_menu(
            self.window.workspace_view.scripts.script_list.currentItem()
        )
        action_names = {
            action.objectName()
            for action in menu.actions()
            if action.objectName()
        }
        self.assertNotIn("scriptContextReveal", action_names)

        with patch(
            "harness_ui.controllers.script_documents.QFileDialog.getSaveFileName",
        ) as save_dialog:
            self.window.script_controller.remove_current()

        save_dialog.assert_not_called()
        self.assertEqual(self.window.workspace_view.scripts.script_list.count(), 1)
        self.assertEqual(self.window.script_controller.current_path, original)
        self.assertEqual(
            self.window.workspace_view.scripts.script_editor.toPlainText(),
            "A desktop harness test.",
        )
        self.assertEqual(
            self.window.statusBar().currentMessage(),
            "Discarded unsaved script",
        )


    def test_script_context_menu_controls_selection_and_file_actions(self):
        self.window = HarnessMainWindow(self.root)
        item = self.window.workspace_view.scripts.script_list.currentItem()
        menu = self.window.script_controller.build_context_menu(item)
        actions = {
            action.objectName(): action
            for action in menu.actions()
            if action.objectName()
        }

        self.assertEqual(
            list(actions),
            [
                "scriptContextInclude",
                "scriptContextSave",
                "scriptContextSaveAs",
                "scriptContextReveal",
                "scriptContextRemove",
                "scriptContextDelete",
            ],
        )
        self.assertTrue(actions["scriptContextInclude"].isChecked())
        self.assertEqual(actions["scriptContextDelete"].text(), "Delete file…")

        actions["scriptContextInclude"].setChecked(False)

        self.assertEqual(item.checkState(), Qt.CheckState.Unchecked)
        self.assertEqual(
            self.window.workspace_view.scripts.script_summary.text(),
            "0 of 1 script will be processed",
        )


    def test_autosave_does_not_recreate_an_externally_deleted_file(self):
        self.window = HarnessMainWindow(self.root)
        script = self.root / "input" / "script.txt"
        self.window.workspace_view.scripts.script_editor.setPlainText("Unsaved replacement.")
        script.unlink()

        self.assertFalse(self.window.script_controller.save())
        self.assertFalse(script.exists())
        self.window.script_controller.dirty = False


    def test_delete_moves_file_to_trash_and_removes_list_entry(self):
        self.window = HarnessMainWindow(self.root)
        script = self.root / "input" / "script.txt"

        def fake_trash(path):
            Path(path).unlink()
            return True

        with (
            patch(
                "harness_ui.dialogs.RecycleBinDialog.confirm",
                return_value=True,
            ),
            patch.object(
                self.window.script_controller,
                "_move_to_trash",
                side_effect=fake_trash,
            ),
        ):
            self.window.script_controller.delete_current()

        self.assertFalse(script.exists())
        self.assertEqual(self.window.workspace_view.scripts.script_list.count(), 0)
        self.assertIsNone(self.window.script_controller.current_path)


if __name__ == "__main__":
    unittest.main()

