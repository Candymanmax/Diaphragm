"""Feature-specific desktop GUI tests."""

from tests.desktop_base import *

class DesktopShellTests(DesktopHarnessBase):
    def test_run_requires_at_least_one_checked_script(self):
        (self.root / "input" / "script.txt").unlink()
        self.window = HarnessMainWindow(self.root)
        header = self.window.workspace_view.header

        self.assertFalse(header.job_header_action.isEnabled())
        self.assertEqual(
            header.job_header_action.toolTip(),
            "Add at least one script to run this job.",
        )
        self.assertFalse(self.window.command_view.action_run.isEnabled())

        script = self.root / "input" / "new-script.txt"
        script.write_text("A runnable script.", encoding="utf-8")
        self.window.script_controller.add_paths((script,))
        self.assertTrue(header.job_header_action.isEnabled())
        self.assertEqual(header.job_header_action.toolTip(), "")
        self.assertTrue(self.window.command_view.action_run.isEnabled())

        item = self.window.workspace_view.scripts.script_list.currentItem()
        item.setCheckState(Qt.CheckState.Unchecked)
        self.assertFalse(header.job_header_action.isEnabled())
        self.assertFalse(self.window.command_view.action_run.isEnabled())


    def test_cross_section_intents_render_through_state_wiring(self):
        self.window = HarnessMainWindow(self.root)
        self.window.show()
        self.application.processEvents()

        self.window.command_view.action_settings.trigger()
        self.assertFalse(self.window.workspace_view.settings.settings_dock.isVisible())
        self.assertEqual(
            self.window.workspace_view.header.settings_toggle_button.accessibleName(),
            "Show job settings inspector",
        )

        self.window.generation_controller.settingsRequested.emit()
        self.assertTrue(self.window.workspace_view.settings.settings_dock.isVisible())
        self.assertEqual(
            self.window.workspace_view.header.settings_toggle_button.accessibleName(),
            "Hide job settings inspector",
        )
        self.window.workspace_view.header.settings_toggle_button.click()
        self.assertFalse(self.window.workspace_view.settings.settings_dock.isVisible())
        self.window.workspace_view.header.settings_toggle_button.click()
        self.assertTrue(self.window.workspace_view.settings.settings_dock.isVisible())

        self.window.generation_controller.tabRequested.emit(1)
        self.assertEqual(self.window.workspace_view.header.work_tabs.currentIndex(), 1)
        self.window.job_controller.tabRequested.emit(2)
        self.assertEqual(self.window.workspace_view.header.work_tabs.currentIndex(), 2)

        self.window.ui_state.set("workspace_error_message", "A test error")
        self.assertTrue(self.window.workspace_view.header.error_banner.isVisible())
        self.assertEqual(self.window.workspace_view.header.error_banner.text(), "A test error")
        self.window.ui_state.set("workspace_error_message", None)
        self.assertFalse(self.window.workspace_view.header.error_banner.isVisible())

    def test_resize_cursor_is_cleared_when_window_deactivates(self):
        self.window = HarnessMainWindow(self.root)
        chrome = self.window._window_chrome
        self.window.setCursor(Qt.CursorShape.SizeHorCursor)
        chrome._last_resize_edges = Qt.Edge.LeftEdge

        self.application.sendEvent(
            self.window,
            QEvent(QEvent.Type.WindowDeactivate),
        )

        self.assertEqual(chrome._last_resize_edges, Qt.Edge(0))
        self.assertEqual(
            self.window.cursor().shape(),
            Qt.CursorShape.ArrowCursor,
        )


    def test_application_icon_asset_is_available(self):
        icon_path = _application_icon_path()

        self.assertTrue(icon_path.is_file())
        self.assertEqual(icon_path.suffix.lower(), ".ico")
        self.assertFalse(QIcon(str(icon_path)).isNull())

        icon_data = icon_path.read_bytes()
        self.assertEqual(icon_data[:4], b"\x00\x00\x01\x00")
        image_count = int.from_bytes(icon_data[4:6], "little")
        icon_sizes = set()
        for image_index in range(image_count):
            entry_offset = 6 + (image_index * 16)
            width = icon_data[entry_offset] or 256
            height = icon_data[entry_offset + 1] or 256
            icon_sizes.add((width, height))

        self.assertTrue(
            {(16, 16), (24, 24), (32, 32), (48, 48), (256, 256)}
            <= icon_sizes
        )


    def test_teal_palette_is_applied_to_primary_interface_elements(self):
        self.assertEqual(TEAL, "#8BD5CA")
        self.assertEqual(ACCENT_START, TEAL)
        self.assertEqual(ACCENT_END, TEAL)
        self.assertEqual(MAIN_BACKGROUND, "#24273A")
        self.assertEqual(PALETTE["crust"], "#181926")
        self.assertEqual(PALETTE["text"], "#CAD3F5")
        self.assertEqual(len(PALETTE), 26)
        stylesheet_colors = {
            value.upper()
            for value in re.findall(r"#[0-9A-Fa-f]{6}", APP_STYLESHEET)
        }
        self.assertLessEqual(stylesheet_colors, set(PALETTE.values()))
        self.assertGreaterEqual(APP_STYLESHEET.count(ACCENT_START), 4)
        self.assertGreaterEqual(APP_STYLESHEET.count(ACCENT_END), 4)

        self.window = HarnessMainWindow(self.root)
        self.assertFalse(hasattr(self.window, "main_toolbar"))
        self.assertFalse(
            [
                button
                for button in self.window.findChildren(QAbstractButton)
                if button.property("accentFill")
            ]
        )
        self.assertEqual(self.window.workspace_view.jobs.job_list.objectName(), "jobList")
        self.assertEqual(self.window.workspace_view.scripts.script_list.objectName(), "scriptList")
        self.assertIn(
            "QListWidget#jobList::item:selected",
            APP_STYLESHEET,
        )
        self.assertIn(
            'QFrame#jobCard[selected="true"]',
            APP_STYLESHEET,
        )
        self.assertIn(
            'QToolButton#jobArchiveButton[hoverHighlightVisible="true"]',
            APP_STYLESHEET,
        )
        self.assertIn(
            "QToolButton#jobArchiveButton,\nQToolButton#scriptRowDeleteButton",
            APP_STYLESHEET,
        )
        self.assertIn("QLabel#jobStatusChip", APP_STYLESHEET)
        self.assertIn("QStackedWidget#jobListStack", APP_STYLESHEET)
        self.assertIn(
            "background: #494D64;",
            APP_STYLESHEET,
        )
        self.assertIn(
            "QTabWidget::pane {\n    border: 0;\n}",
            APP_STYLESHEET,
        )
        self.assertIn(
            "border-bottom: 2px solid transparent",
            APP_STYLESHEET,
        )
        self.assertIn(
            "QListWidget#scriptList::item:selected",
            APP_STYLESHEET,
        )


    def test_buttons_use_consistent_visual_roles(self):
        self.window = HarnessMainWindow(self.root)
        settings_button = self.window.workspace_view.header.settings_toggle_button

        self.assertEqual(
            self.window.workspace_view.header.job_header_action.property("buttonRole"),
            "primary",
        )
        self.assertFalse(settings_button.icon().isNull())
        self.assertEqual(settings_button.width(), settings_button.height())
        self.assertEqual(
            settings_button.height(),
            self.window.workspace_view.header.job_header_action.sizeHint().height(),
        )
        self.assertEqual(self.window.workspace_view.scripts.script_save_action.text(), "Save")
        self.assertEqual(
            self.window.workspace_view.scripts.new_script_button.property("buttonRole"),
            "neutral",
        )
        self.assertEqual(
            self.window.workspace_view.output.open_output_folder_button.property("buttonRole"),
            "neutral",
        )
        self.assertEqual(
            self.window.workspace_view.queue.restart_button.property("buttonRole"),
            "neutral",
        )
        self.assertEqual(
            self.window.workspace_view.scripts.save_as_button.property("buttonRole"),
            "neutral",
        )
        self.assertEqual(
            self.window.workspace_view.scripts.script_menu_button.property("buttonRole"),
            "neutral",
        )
        self.assertEqual(
            self.window.workspace_view.scripts.delete_script_button.property("buttonRole"),
            "danger",
        )
        self.assertEqual(
            self.window.workspace_view.scripts.delete_script_button.objectName(),
            "scriptDeleteButton",
        )
        self.assertEqual(
            self.window.workspace_view.scripts.delete_script_button.text(),
            "",
        )
        self.assertFalse(
            self.window.workspace_view.scripts.delete_script_button.icon().isNull()
        )
        self.assertEqual(
            self.window.workspace_view.scripts.delete_script_button.accessibleName(),
            "Delete script",
        )
        self.assertEqual(
            self.window.workspace_view.scripts.delete_script_button.size(),
            QSize(36, 36),
        )
        self.assertEqual(
            self.window.workspace_view.scripts.delete_script_button.toolTip(),
            "",
        )
        self.assertEqual(
            self.window.workspace_view.scripts.script_menu_button.size(),
            QSize(36, 36),
        )
        self.assertEqual(
            self.window.workspace_view.settings.settings_panel.save_button.property("buttonRole"),
            "primary",
        )
        self.assertFalse(
            self.window.workspace_view.settings.settings_panel.save_button.property(
                "accentFill"
            )
        )
        self.assertEqual(
            self.window.workspace_view.settings.settings_panel.reset_button.property("buttonRole"),
            "neutral",
        )

        with self.assertRaisesRegex(ValueError, "Unknown button role"):
            set_button_role(self.window.workspace_view.scripts.new_script_button, "unknown")


    def test_script_workspace_is_compact_and_hides_personal_paths(self):
        self.window = HarnessMainWindow(self.root)
        self.window.resize(1200, 720)
        self.window.show()
        self.application.processEvents()

        self.assertGreaterEqual(self.window.workspace_view.scripts.script_list.width(), 220)
        self.assertLessEqual(self.window.workspace_view.scripts.script_list.width(), 260)
        self.assertEqual(
            self.window.workspace_view.scripts.script_list.item(0).text(),
            "script.txt\n4 words",
        )
        self.assertEqual(self.window.workspace_view.scripts.editor_path.text(), "input/script.txt")
        self.assertNotIn(str(self.root), self.window.workspace_view.scripts.editor_path.text())
        self.assertEqual(
            self.window.workspace_view.scripts.editor_path.toolTip(),
            "",
        )
        self.assertEqual(
            self.window.workspace_view.scripts.script_list.item(0).toolTip(),
            "",
        )
        self.assertEqual(
            [
                action.text()
                for action in self.window.workspace_view.scripts.script_menu.actions()
                if not action.isSeparator()
            ],
            [
                "Save",
                "Add scripts…",
                "Show line numbers",
            ],
        )
        self.assertEqual(self.window.workspace_view.scripts.script_save_state.text(), "Saved")


    def test_script_editor_has_writing_aids_and_toggleable_line_numbers(self):
        self.window = HarnessMainWindow(self.root)
        self.window.show()
        self.application.processEvents()
        editor = self.window.workspace_view.scripts.script_editor

        self.assertGreaterEqual(editor.font().pointSizeF(), 11.0)
        self.assertEqual(editor.objectName(), "scriptEditor")
        self.assertEqual(editor.textCursor().blockFormat().lineHeight(), 125.0)
        self.assertTrue(editor.line_numbers_visible())
        self.assertGreater(editor.line_number_area_width(), 0)
        self.assertEqual(len(editor.extraSelections()), 1)

        self.window.workspace_view.scripts.script_line_numbers_action.setChecked(False)
        self.assertFalse(editor.line_numbers_visible())
        self.assertEqual(editor.line_number_area_width(), 0)


    def test_empty_script_editor_uses_centered_drop_hint_without_a_tooltip(self):
        self.window = HarnessMainWindow(self.root)
        self.window.show()
        self.application.processEvents()
        scripts = self.window.workspace_view.scripts

        scripts.script_list.clear()
        self.application.processEvents()

        self.assertEqual(scripts.script_list.count(), 0)
        self.assertEqual(
            scripts.editor_empty_state.message_label.text(),
            "Drop a .txt file here, or choose an option below.",
        )
        self.assertEqual(scripts.editor_empty_state.action_button.text(), "New script")
        self.assertEqual(
            scripts.editor_empty_state.secondary_action_button.text(),
            "Browse files…",
        )
        self.assertTrue(scripts.editor_empty_state.action_button.isVisible())
        self.assertTrue(
            scripts.editor_empty_state.secondary_action_button.isVisible()
        )
        self.assertEqual(
            scripts.editor_empty_state.action_button.property("buttonRole"),
            "primary",
        )
        self.assertEqual(
            scripts.editor_empty_state.secondary_action_button.property("buttonRole"),
            "neutral",
        )
        self.assertIs(
            scripts.editor_stack.currentWidget(),
            scripts.editor_empty_state,
        )
        self.assertEqual(scripts.script_list.toolTip(), "")
        self.assertFalse(bool(scripts.script_list.property("dropActive")))


    def test_menu_bar_exposes_global_actions_and_view_controls(self):
        self.window = HarnessMainWindow(self.root)
        self.window.resize(1200, 720)
        self.window.show()
        self.application.processEvents()

        self.assertEqual(
            [
                self.window.command_view.file_menu.title(),
                self.window.command_view.edit_menu.title(),
                self.window.command_view.view_menu.title(),
                self.window.command_view.settings_menu.title(),
                self.window.command_view.help_menu.title(),
            ],
            ["File", "Edit", "View", "Settings", "Help"],
        )
        self.assertFalse(hasattr(self.window, "main_toolbar"))
        self.assertIn(
            self.window.command_view.action_new_job,
            self.window.command_view.file_menu.actions(),
        )
        self.assertIn(
            self.window.command_view.action_add_scripts,
            self.window.command_view.file_menu.actions(),
        )
        self.assertIn(
            self.window.command_view.action_run,
            self.window.command_view.file_menu.actions(),
        )
        self.assertEqual(
            [action.text() for action in self.window.command_view.sections_menu.actions()],
            ["Toggle sidebar", "Settings", "Logs"],
        )
        self.assertIn(
            self.window.command_view.action_refresh,
            self.window.command_view.view_menu.actions(),
        )
        self.assertEqual(
            self.window.command_view.settings_menu.actions(),
            [self.window.command_view.action_preferences],
        )
        self.assertEqual(
            self.window.command_view.action_preferences.shortcut(),
            QKeySequence("Ctrl+,"),
        )
        self.assertTrue(self.window.command_view.action_settings.shortcut().isEmpty())
        self.assertTrue(self.window.workspace_view.jobs.sidebar_panel.isVisible())
        self.window.command_view.sidebar_toggle_button.click()
        self.assertFalse(self.window.workspace_view.jobs.sidebar_panel.isVisible())
        self.window.command_view.view_sidebar_action.trigger()
        self.assertTrue(self.window.workspace_view.jobs.sidebar_panel.isVisible())
        self.assertIn(
            self.window.command_view.accent_actions["teal"],
            self.window.command_view.view_accent_menu.actions(),
        )


    def test_accent_menu_uses_only_decorative_palette_colors(self):
        self.window = HarnessMainWindow(self.root)
        expected_names = [
            "rosewater",
            "flamingo",
            "pink",
            "mauve",
            "red",
            "maroon",
            "peach",
            "yellow",
            "green",
            "teal",
            "sky",
            "sapphire",
            "blue",
            "lavender",
        ]

        self.assertEqual(list(ACCENT_COLORS), expected_names)
        self.assertEqual(list(self.window.command_view.accent_actions), expected_names)
        self.assertTrue(self.window.command_view.accent_actions["teal"].isChecked())
        self.assertEqual(self.window.command_view.accent_actions["teal"].text(), "Teal")
        self.assertFalse(self.window.command_view.accent_actions["teal"].icon().isNull())

        excluded = {
            "text",
            "subtext_1",
            "subtext_0",
            "overlay_2",
            "overlay_1",
            "overlay_0",
            "surface_2",
            "surface_1",
            "surface_0",
            "base",
            "mantle",
            "crust",
        }
        self.assertTrue(excluded.isdisjoint(self.window.command_view.accent_actions))

        self.window.command_view.accent_actions["mauve"].trigger()

        self.assertEqual(self.window.ui_state.get("accent_name"), "mauve")
        self.assertTrue(self.window.command_view.accent_actions["mauve"].isChecked())
        self.assertEqual(
            self.application.property("ttsAccentColor"),
            ACCENT_COLORS["mauve"],
        )
        self.assertEqual(
            self.application.styleSheet(),
            build_stylesheet("mauve"),
        )


