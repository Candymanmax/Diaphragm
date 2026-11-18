"""Mac desktop behavior and Windows frame regression checks."""

import sys
from unittest import skipUnless
from unittest.mock import Mock, patch

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QDialog, QMenuBar

from tests.desktop_base import DesktopHarnessBase, HarnessMainWindow, Qt
from modules.app_settings import CredentialStore, CredentialStoreError
from modules.platform_support import credential_store_name, trash_name


class MacDesktopTests(DesktopHarnessBase):
    def mac_window(self):
        with patch.object(sys, "platform", "darwin"):
            self.window = HarnessMainWindow(self.root)
        return self.window

    def test_mac_uses_native_frame_and_keeps_sidebar_control_in_workspace(self):
        window = self.mac_window()
        self.assertFalse(window.windowFlags() & Qt.WindowType.FramelessWindowHint)
        self.assertIsNone(window._window_chrome.title_bar)
        self.assertIsInstance(window.command_view.app_menu_bar, QMenuBar)
        self.assertEqual(
            window.workspace_view.header.header_row.indexOf(window.command_view.sidebar_toggle_button), 0
        )
        window.show()
        self.application.processEvents()
        window.command_view.sidebar_toggle_button.click()
        self.assertFalse(window.workspace_view.jobs.sidebar_panel.isVisible())
        window.command_view.view_sidebar_action.trigger()
        self.assertTrue(window.workspace_view.jobs.sidebar_panel.isVisible())

    @skipUnless(sys.platform == "darwin", "Cocoa fullscreen-button flag is macOS-only")
    def test_mac_frame_keeps_the_native_fullscreen_button(self):
        window = self.mac_window()
        self.assertTrue(window.windowFlags() & Qt.WindowType.WindowFullscreenButtonHint)

    def test_windows_keeps_the_custom_caption_and_menu_strip(self):
        with patch.object(sys, "platform", "win32"):
            self.window = HarnessMainWindow(self.root)
        self.assertTrue(self.window.windowFlags() & Qt.WindowType.FramelessWindowHint)
        self.assertIsNotNone(self.window._window_chrome.title_bar)
        self.assertFalse(isinstance(self.window.command_view.app_menu_bar, QMenuBar))
        self.assertFalse(hasattr(self.window.command_view, "window_menu_toolbar"))

    def test_mac_window_menu_row_is_visible_above_the_workspace(self):
        window = self.mac_window()
        window.show()
        self.application.processEvents()
        commands = window.command_view
        toolbar = commands.window_menu_toolbar
        self.assertTrue(toolbar.isVisible())
        self.assertFalse(toolbar.isMovable())
        self.assertFalse(toolbar.isFloatable())
        self.assertGreaterEqual(window.centralWidget().geometry().top(), toolbar.geometry().bottom())
        self.assertEqual(
            [menu.title() for menu in commands.window_menu_strip._menu_buttons],
            ["File", "Edit", "View", "Settings", "Window", "Help"],
        )

    def test_window_menus_share_command_state_with_native_menus(self):
        window = self.mac_window()
        commands = window.command_view
        menus = list(commands.window_menu_strip._menu_buttons)
        self.assertIn(commands.action_run, menus[0].actions())
        commands.action_run.setEnabled(False)
        self.assertFalse(menus[0].actions()[4].isEnabled())
        sections = menus[2].actions()[0].menu()
        self.assertIsNot(sections, commands.sections_menu)
        self.assertIs(sections.actions()[0], commands.view_sidebar_action)
        window.show()
        self.application.processEvents()
        sections.actions()[0].trigger()
        self.assertFalse(window.workspace_view.jobs.sidebar_panel.isVisible())
        with patch.object(commands, "refresh_edit_actions") as refresh:
            # The original signal carries the same live update used by Cocoa.
            commands.edit_menu.aboutToShow.connect(refresh)
            menus[1].aboutToShow.emit()
        refresh.assert_called_once()

    def test_mac_menu_roles_shortcuts_and_native_labels(self):
        commands = self.mac_window().command_view
        self.assertEqual(commands.action_preferences.menuRole(), QAction.MenuRole.PreferencesRole)
        self.assertEqual(commands.action_about.menuRole(), QAction.MenuRole.AboutRole)
        self.assertEqual(commands.action_quit.menuRole(), QAction.MenuRole.QuitRole)
        self.assertEqual(commands.action_close.shortcut(), QKeySequence(QKeySequence.StandardKey.Close))
        self.assertEqual(commands.action_quit.shortcut(), QKeySequence(QKeySequence.StandardKey.Quit))
        self.assertEqual(commands.action_fullscreen.shortcut(), QKeySequence(QKeySequence.StandardKey.FullScreen))
        self.assertEqual(commands.action_fullscreen.menuRole(), QAction.MenuRole.NoRole)
        self.assertIn(
            commands.action_run.shortcut().toString(QKeySequence.SequenceFormat.NativeText),
            commands.run_tooltip(),
        )

    def test_fullscreen_can_return_to_a_normal_window(self):
        window = self.mac_window()
        window.show()
        self.application.processEvents()
        window.command_view.action_fullscreen.trigger()
        self.application.processEvents()
        self.assertTrue(window.isFullScreen())
        window.command_view.action_fullscreen.trigger()
        self.application.processEvents()
        self.assertFalse(window.isFullScreen())

    def test_quit_menu_uses_unsaved_script_exit_guard(self):
        window = self.mac_window()
        window.show()
        self.application.processEvents()
        with patch.object(window.script_controller, "exit_requires_confirmation", return_value=True), patch.object(
            window.shutdown_controller, "confirm_unsaved_exit", return_value=False
        ) as confirm:
            window.command_view.action_quit.trigger()
            self.application.processEvents()
        confirm.assert_called_once()
        self.assertTrue(window.isVisible())

    def test_close_window_targets_an_active_dialog(self):
        window = self.mac_window()
        window.show()
        dialog = QDialog(window)
        dialog.show()
        dialog.activateWindow()
        self.application.processEvents()
        with patch.object(window, "close") as close_main:
            window.command_view.action_close.trigger()
        self.assertFalse(dialog.isVisible())
        self.assertTrue(window.isVisible())
        close_main.assert_not_called()

    def test_native_edit_menu_routes_to_the_focused_editor(self):
        window = self.mac_window()
        window.show()
        editor = window.workspace_view.scripts.script_editor
        editor.setPlainText("A disposable test sentence.")
        editor.setFocus()
        self.application.processEvents()
        window.command_view.edit_actions["selectAll"].trigger()
        self.assertEqual(editor.textCursor().selectedText(), "A disposable test sentence.")

    def test_platform_terms_and_keychain_failure_messages(self):
        for platform_name, storage, trash in (
            ("darwin", "macOS Keychain", "Trash"),
            ("win32", "Windows Credential Manager", "Recycle Bin"),
        ):
            with self.subTest(platform=platform_name), patch.object(sys, "platform", platform_name):
                self.assertEqual(credential_store_name(), storage)
                self.assertEqual(trash_name(), trash)
                backend = Mock()
                backend.get_password.side_effect = RuntimeError("denied")
                with self.assertRaisesRegex(CredentialStoreError, storage):
                    CredentialStore(backend).token()
