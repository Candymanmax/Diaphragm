import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from harness_ui.main_window import HarnessMainWindow
from harness_ui.preferences import PreferencesDialog, _TokenVerifyTask
from modules.app_settings import CredentialStore


class _MemoryKeyring:
    def __init__(self):
        self.values = {}

    def get_password(self, service, name):
        return self.values.get((service, name))

    def set_password(self, service, name, value):
        self.values[(service, name)] = value

    def delete_password(self, service, name):
        self.values.pop((service, name), None)


class PreferencesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.application = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "input").mkdir()
        (self.root / "voices").mkdir()
        (self.root / "input" / "script.txt").write_text(
            "A Preferences window test.",
            encoding="utf-8",
        )
        (self.root / "voices" / "voice.wav").write_bytes(b"voice")
        (self.root / "config.default.yaml").write_text(
            "voice: voice.wav\nmodel: original\nlanguage: en\n",
            encoding="utf-8",
        )
        self.credential_store = CredentialStore(_MemoryKeyring())
        self.credential_patch = patch(
            "harness_ui.preferences.dialog.CredentialStore",
            return_value=self.credential_store,
        )
        self.credential_patch.start()
        self.addCleanup(self.credential_patch.stop)
        self.window = HarnessMainWindow(self.root)
        self.window.show()
        self.application.processEvents()

    def tearDown(self):
        dialog = self.window.ui_state.get("preferences_dialog")

        if dialog is not None:
            self._wait_for(
                lambda: not any(
                    thread.isRunning()
                    for thread, _task in dialog.background_tasks
                ),
                timeout=5,
            )
            dialog.close()
            self.application.processEvents()

        self.window.close()
        self.application.processEvents()

    def _wait_for(self, predicate, timeout=3):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            self.application.processEvents()

            if predicate():
                return True

            QTest.qWait(20)

        return bool(predicate())

    def open_preferences(self):
        self.window.command_view.action_preferences.trigger()
        self.application.processEvents()
        return self.window.ui_state.get("preferences_dialog")

    def test_preferences_action_is_singleton_frameless_and_uses_ctrl_comma(self):
        first = self.open_preferences()

        self.assertIsInstance(first, PreferencesDialog)
        self.assertEqual(
            self.window.command_view.action_preferences.shortcut(),
            QKeySequence("Ctrl+,"),
        )
        self.assertTrue(first.windowFlags() & Qt.WindowType.FramelessWindowHint)
        self.assertEqual(first.navigation.count(), 7)
        self.assertEqual(first.pages.count(), 7)
        self.assertEqual(first.PAGE_NAMES[3], "Models")

        self.window.command_view.action_preferences.trigger()
        self.application.processEvents()

        self.assertIs(self.window.ui_state.get("preferences_dialog"), first)
        first.close()
        self.application.processEvents()
        self.assertTrue(self.window.isVisible())

    def test_models_page_has_all_models_and_accurate_local_size_only(self):
        dialog = self.open_preferences()
        manager = dialog.model_manager

        self.assertEqual(
            tuple(manager.cards),
            ("original", "turbo", "v3", "nano"),
        )

        for card in manager.cards.values():
            self.assertIn("Local files:", card.local_size_label.text())
            self.assertNotIn("Required", card.local_size_label.text())
            self.assertEqual(
                tuple(card.buttons),
                ("install", "update", "verify", "repair", "remove"),
            )

    def test_model_install_uses_progress_bar_and_explicit_cache(self):
        dialog = self.open_preferences()
        manager = dialog.model_manager
        card = manager.cards["turbo"]

        with patch.object(manager.process, "start") as start:
            self.assertTrue(
                manager.request_operation("turbo", "install", confirm=False)
            )
            manager._handle_process_line("MODEL_PROGRESS 83")

        executable, arguments = start.call_args.args
        self.assertTrue(executable)
        self.assertEqual(arguments[:3], ("-m", "modules.model_download", "turbo"))
        self.assertIn("--cache-root", arguments)
        self.assertEqual(card.progress.value(), 83)
        self.assertIn("Installing", card.progress.format())
        self.assertFalse(card.progress.isHidden())
        manager._complete_process(-1)

    def test_model_manager_reports_the_correct_external_blocker(self):
        dialog = self.open_preferences()
        manager = dialog.model_manager
        card = manager.cards["turbo"]

        manager.model_busy = lambda: True
        self.assertFalse(
            manager.request_operation("turbo", "install", confirm=False)
        )
        self.assertIn("current model operation", card.status_label.text())

        manager.model_busy = lambda: False
        manager.worker_running = lambda: True
        self.assertFalse(
            manager.request_operation("turbo", "install", confirm=False)
        )
        self.assertIn("active generation job", card.status_label.text())

    def test_inline_model_operation_refreshes_the_open_models_page(self):
        dialog = self.open_preferences()
        manager = dialog.model_manager
        panel = self.window.workspace_view.settings.settings_panel
        panel.model.setCurrentIndex(panel.model.findData("nano"))
        card = manager.cards["nano"]

        def start_operation(_executable, _arguments):
            snapshot = (
                self.root
                / "models"
                / "huggingface"
                / "hub"
                / "models--ResembleAI--chatterbox-nano"
                / "snapshots"
                / "revision"
            )
            snapshot.mkdir(parents=True)
            (snapshot / "vocab.json").write_bytes(b"partial")

        with (
            patch(
                "harness_ui.settings.models.AppDialog.confirm",
                return_value=True,
            ),
            patch.object(
                panel.model_controller.process,
                "start",
                side_effect=start_operation,
            ),
        ):
            panel.model_install_button.click()

        self.assertEqual(card.state_badge.text(), "Needs repair")
        self.assertIn("1/6 required", card.status_label.text())

    def test_preferences_model_operation_locks_the_inline_button(self):
        dialog = self.open_preferences()
        manager = dialog.model_manager
        panel = self.window.workspace_view.settings.settings_panel
        panel.model.setCurrentIndex(panel.model.findData("turbo"))

        with patch.object(manager.process, "start"):
            self.assertTrue(
                manager.request_operation("turbo", "install", confirm=False)
            )
            self.assertFalse(panel.model_install_button.isEnabled())
            manager._complete_process(-1)

        self.assertTrue(panel.model_install_button.isEnabled())

    def test_appearance_startup_and_panel_changes_apply_immediately(self):
        dialog = self.open_preferences()
        dialog.startup_behavior.setCurrentIndex(
            dialog.startup_behavior.findData("blank")
        )
        dialog.accent.setCurrentIndex(dialog.accent.findData("blue"))
        dialog.show_line_numbers.setChecked(False)
        dialog.show_sidebar.setChecked(False)
        dialog.show_settings.setChecked(False)
        dialog.show_logs.setChecked(True)
        self.application.processEvents()

        preferences = self.window.settings_repository.preferences()
        self.assertEqual(preferences.startup_behavior, "blank")
        self.assertEqual(preferences.accent, "blue")
        self.assertFalse(preferences.show_line_numbers)
        self.assertFalse(preferences.sidebar_visible)
        self.assertFalse(preferences.settings_visible)
        self.assertTrue(preferences.logs_visible)
        self.assertEqual(self.window.ui_state.get("accent_name"), "blue")
        self.assertFalse(self.window.workspace_view.scripts.script_editor.line_numbers_visible())
        self.assertFalse(self.window.workspace_view.jobs.sidebar_panel.isVisible())
        self.assertFalse(self.window.workspace_view.settings.settings_dock.isVisible())
        self.assertTrue(self.window.workspace_view.logs.logs_dock.isVisible())

    def test_no_update_or_token_network_call_occurs_until_button_press(self):
        self.credential_store.set_token("test-token")

        with (
            patch(
                "harness_ui.preferences.values.QDesktopServices.openUrl"
            ) as open_url,
            patch("huggingface_hub.HfApi.whoami", return_value={"name": "tester"}) as whoami,
        ):
            dialog = self.open_preferences()
            self.application.processEvents()
            open_url.assert_not_called()
            whoami.assert_not_called()

            dialog.open_releases_button.click()
            open_url.assert_called_once()
            whoami.assert_not_called()

            dialog.verify_token_button.click()
            self.assertTrue(self._wait_for(lambda: whoami.called, timeout=5))

    def test_credential_status_uses_service_card_and_state_badge(self):
        dialog = self.open_preferences()

        self.assertEqual(
            dialog.token_status.property("credentialState"),
            "unconfigured",
        )
        self.assertEqual(dialog.token_status.text(), "Not configured")
        self.assertEqual(
            dialog.token_status.objectName(),
            "credentialStatusBadge",
        )

        self.credential_store.set_token("test-token")
        dialog.credentials_controller.refresh_status()

        self.assertEqual(
            dialog.token_status.property("credentialState"),
            "configured",
        )
        self.assertEqual(dialog.token_status.text(), "Configured")

    def test_token_verification_errors_redact_the_token(self):
        token = "test-secret-value"
        messages = []
        task = _TokenVerifyTask(token)
        task.failed.connect(messages.append)

        with patch(
            "huggingface_hub.HfApi.whoami",
            side_effect=RuntimeError(f"rejected {token}"),
        ):
            task.run()

        self.assertEqual(len(messages), 1)
        self.assertNotIn(token, messages[0])
        self.assertIn("<redacted>", messages[0])

    def test_preferences_layout_survives_common_scale_factors(self):
        code = """
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from PySide6.QtWidgets import QApplication
from harness_ui.main_window import HarnessMainWindow

with TemporaryDirectory() as value:
    root = Path(value)
    (root / 'input').mkdir()
    (root / 'voices').mkdir()
    (root / 'config.default.yaml').write_text(
        'voice: voice.wav\\nmodel: original\\nlanguage: en\\n',
        encoding='utf-8',
    )
    (root / 'voices' / 'voice.wav').write_bytes(b'voice')
    app = QApplication([])
    window = HarnessMainWindow(root)
    window.command_view.action_preferences.trigger()
    app.processEvents()
    dialog = window.ui_state.get("preferences_dialog")
    assert dialog.width() >= dialog.minimumWidth()
    assert dialog.height() >= dialog.minimumHeight()
    assert dialog.pages.width() > dialog.navigation.width()
    dialog.prepare_for_application_exit()
    window.close()
"""

        for factor in ("1", "1.25", "1.5"):
            environment = os.environ.copy()
            environment["QT_QPA_PLATFORM"] = "offscreen"
            environment["QT_SCALE_FACTOR"] = factor
            result = subprocess.run(
                [sys.executable, "-c", code],
                cwd=Path(__file__).resolve().parents[1],
                env=environment,
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            self.assertEqual(
                result.returncode,
                0,
                msg=f"scale {factor}: {result.stdout}\n{result.stderr}",
            )


if __name__ == "__main__":
    unittest.main()
