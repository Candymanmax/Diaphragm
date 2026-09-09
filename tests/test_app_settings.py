import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PySide6.QtCore import QSettings

from modules.app_settings import migration as app_settings_migration
from modules.app_settings import (
    AppPaths,
    CredentialStore,
    DiagnosticLogStore,
    PathMigrationError,
    SettingsError,
    SettingsRepository,
    migrate_library,
    migrate_model_cache,
)


class _MemoryKeyring:
    def __init__(self):
        self.values = {}

    def get_password(self, service, name):
        return self.values.get((service, name))

    def set_password(self, service, name, value):
        self.values[(service, name)] = value

    def delete_password(self, service, name):
        self.values.pop((service, name), None)


class AppSettingsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = self.root / "project"
        self.project.mkdir()
        (self.project / "config.default.yaml").write_text(
            "voice: voice.wav\nmodel: original\nlanguage: en\n",
            encoding="utf-8",
        )
        self.settings = QSettings(
            str(self.root / "preferences.ini"),
            QSettings.Format.IniFormat,
        )
        self.settings.clear()

    def tearDown(self):
        self.settings.clear()
        self.settings.sync()

    def repository(self):
        return SettingsRepository.for_testing(
            self.project,
            settings=self.settings,
        )

    def test_typed_preferences_persist_and_reject_invalid_values(self):
        repository = self.repository()
        repository.set_value("startup/behavior", "blank")
        repository.set_value("ui/accent", "mauve")
        repository.set_value("editor/show_line_numbers", False)
        repository.set_value("ui/sidebar_visible", False)
        repository.set_value("ui/settings_visible", False)
        repository.set_value("ui/logs_visible", True)
        repository.set_value("storage/low_disk_warning_gb", 25)
        repository.set_value("storage/log_retention_days", 30)

        preferences = repository.preferences()
        self.assertEqual(preferences.startup_behavior, "blank")
        self.assertEqual(preferences.accent, "mauve")
        self.assertFalse(preferences.show_line_numbers)
        self.assertFalse(preferences.sidebar_visible)
        self.assertFalse(preferences.settings_visible)
        self.assertTrue(preferences.logs_visible)
        self.assertEqual(preferences.low_disk_warning_gb, 25)
        self.assertEqual(preferences.log_retention_days, 30)

        with self.assertRaises(SettingsError):
            repository.set_value("startup/behavior", "surprise")

        with self.assertRaises(SettingsError):
            repository.set_value("storage/low_disk_warning_gb", 0)

    def test_reset_preferences_preserves_all_personal_data_and_paths(self):
        repository = self.repository()
        protected = (
            repository.paths.input_root / "script.txt",
            repository.paths.voices_root / "voice.wav",
            repository.paths.jobs_root / "job-1" / "manifest.json",
            repository.paths.outputs_root / "published.wav",
            repository.paths.model_cache_root / "weights.bin",
        )

        for path in protected:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"keep")

        library_path = repository.paths.library_root
        model_path = repository.paths.model_cache_root
        repository.set_value("ui/accent", "red")
        repository.reset_application_preferences()

        self.assertEqual(repository.preferences().accent, "teal")
        self.assertEqual(repository.paths.library_root, library_path)
        self.assertEqual(repository.paths.model_cache_root, model_path)
        self.assertTrue(all(path.is_file() for path in protected))

    def test_application_uses_local_data_and_ignores_project_data(self):
        local_app_data = self.root / "local"
        active_config = self.project / "config.yaml"
        active_config.write_text(
            "voice: private.wav\nmodel: original\nlanguage: en\n",
            encoding="utf-8",
        )
        (self.project / "models").mkdir()
        (self.project / "models" / "cached.bin").write_bytes(b"model")
        current = QSettings(
            str(self.root / "current.ini"),
            QSettings.Format.IniFormat,
        )

        with (
            patch.dict(os.environ, {"LOCALAPPDATA": str(local_app_data)}),
        ):
            repository = SettingsRepository.for_application(
                self.project,
                settings=current,
                defaults_file=self.project / "config.default.yaml",
            )

        self.assertEqual(
            repository.paths.library_root,
            (local_app_data / "Diaphragm").resolve(),
        )
        self.assertEqual(
            repository.paths.model_cache_root,
            (local_app_data / "Diaphragm" / "models").resolve(),
        )
        migrated = local_app_data / "Diaphragm" / "config.yaml"
        self.assertEqual(
            migrated.read_bytes(),
            (self.project / "config.default.yaml").read_bytes(),
        )
        self.assertTrue(active_config.is_file())
        self.assertFalse(current.contains("migration/local_harness_settings"))

    def test_clean_install_uses_local_app_data_for_library_and_models(self):
        clean_project = self.root / "clean-install"
        clean_project.mkdir()
        defaults = clean_project / "config.default.yaml"
        defaults.write_text(
            "voice: voice.wav\nmodel: original\nlanguage: en\n",
            encoding="utf-8",
        )
        local_app_data = self.root / "local"
        settings = QSettings(
            str(self.root / "clean.ini"),
            QSettings.Format.IniFormat,
        )

        with (
            patch.dict(os.environ, {"LOCALAPPDATA": str(local_app_data)}),
        ):
            repository = SettingsRepository.for_application(
                clean_project,
                settings=settings,
                defaults_file=defaults,
            )

        self.assertEqual(
            repository.paths.data_root,
            (local_app_data / "Diaphragm").resolve(),
        )
        self.assertEqual(
            repository.paths.library_root,
            (local_app_data / "Diaphragm").resolve(),
        )
        self.assertEqual(
            repository.paths.model_cache_root,
            (local_app_data / "Diaphragm" / "models").resolve(),
        )
        self.assertTrue(repository.paths.config_file.is_file())

    def test_library_migration_suffixes_files_and_remaps_job_ids(self):
        source = self.root / "source"
        destination = self.root / "destination"
        (source / "input").mkdir(parents=True)
        (source / "input" / "story.txt").write_text(
            "source story",
            encoding="utf-8",
        )
        source_job = source / "jobs" / "job-1"
        source_job.mkdir(parents=True)
        (source_job / "manifest.json").write_text(
            json.dumps({"job_id": "job-1", "name": "Source"}),
            encoding="utf-8",
        )
        (source_job / "audio.wav").write_bytes(b"source audio")
        (destination / "input").mkdir(parents=True)
        (destination / "input" / "story.txt").write_text(
            "different story",
            encoding="utf-8",
        )
        destination_job = destination / "jobs" / "job-1"
        destination_job.mkdir(parents=True)
        (destination_job / "manifest.json").write_text(
            json.dumps({"job_id": "job-1", "name": "Destination"}),
            encoding="utf-8",
        )

        report = migrate_library(source, destination)

        self.assertGreaterEqual(report.copied_files, 3)
        self.assertEqual(
            (destination / "input" / "story-imported-2.txt").read_text(
                encoding="utf-8"
            ),
            "source story",
        )
        imported_job = destination / "jobs" / "job-1-imported-2"
        manifest = json.loads(
            (imported_job / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["job_id"], "job-1-imported-2")
        self.assertEqual((imported_job / "audio.wav").read_bytes(), b"source audio")
        self.assertEqual(
            json.loads((source_job / "manifest.json").read_text(encoding="utf-8"))["job_id"],
            "job-1",
        )

        repeated = migrate_library(source, destination)

        self.assertGreaterEqual(repeated.skipped_files, 3)
        self.assertFalse(
            (destination / "jobs" / "job-1-imported-3").exists()
        )

    def test_library_migration_skips_identical_files(self):
        source = self.root / "source"
        destination = self.root / "destination"
        (source / "voices").mkdir(parents=True)
        (destination / "voices").mkdir(parents=True)
        (source / "voices" / "same.wav").write_bytes(b"same")
        (destination / "voices" / "same.wav").write_bytes(b"same")

        with patch(
            "modules.app_settings.migration.shutil.disk_usage",
            return_value=SimpleNamespace(free=0),
        ):
            report = migrate_library(source, destination)

        self.assertEqual(report.copied_files, 0)
        self.assertEqual(report.skipped_files, 1)

    def test_library_migration_rejects_nested_and_insufficient_destinations(self):
        source = self.root / "source"
        (source / "input").mkdir(parents=True)
        (source / "input" / "story.txt").write_bytes(b"content")

        with self.assertRaisesRegex(PathMigrationError, "cannot be inside"):
            migrate_library(source, source / "nested")

        with patch(
            "modules.app_settings.migration.shutil.disk_usage",
            return_value=SimpleNamespace(free=0),
        ):
            with self.assertRaisesRegex(PathMigrationError, "free space"):
                migrate_library(source, self.root / "destination")

    def test_interrupted_library_copy_can_resume_from_verified_staging(self):
        source = self.root / "source"
        destination = self.root / "destination"
        (source / "input").mkdir(parents=True)
        (source / "input" / "one.txt").write_bytes(b"one")
        (source / "input" / "two.txt").write_bytes(b"two")
        real_copy = app_settings_migration._atomic_copy
        calls = 0

        def interrupted_copy(first, second):
            nonlocal calls
            calls += 1
            real_copy(first, second)

            if calls == 1:
                raise OSError("simulated interruption")

        with patch(
            "modules.app_settings.migration._atomic_copy",
            interrupted_copy,
        ):
            with self.assertRaisesRegex(OSError, "simulated interruption"):
                migrate_library(source, destination)

        report = migrate_library(source, destination)

        self.assertEqual(report.copied_files, 2)
        self.assertEqual((destination / "input" / "one.txt").read_bytes(), b"one")
        self.assertEqual((destination / "input" / "two.txt").read_bytes(), b"two")
        self.assertEqual((source / "input" / "one.txt").read_bytes(), b"one")

    def test_model_cache_migration_verifies_copy_without_deleting_source(self):
        source = self.root / "models"
        destination = self.root / "new-models"
        (source / "hub" / "snapshot").mkdir(parents=True)
        weights = source / "hub" / "snapshot" / "weights.safetensors"
        weights.write_bytes(b"model")

        report = migrate_model_cache(source, destination)

        self.assertEqual(report.copied_files, 1)
        self.assertEqual(
            (destination / "hub" / "snapshot" / weights.name).read_bytes(),
            b"model",
        )
        self.assertTrue(weights.is_file())

        conflict_destination = self.root / "conflicting-models"
        conflict = (
            conflict_destination / "hub" / "snapshot" / weights.name
        )
        conflict.parent.mkdir(parents=True)
        conflict.write_bytes(b"different")

        with self.assertRaisesRegex(PathMigrationError, "different file"):
            migrate_model_cache(source, conflict_destination)

        self.assertEqual(weights.read_bytes(), b"model")
        self.assertEqual(conflict.read_bytes(), b"different")

    def test_credentials_use_only_the_secure_storage_abstraction(self):
        backend = _MemoryKeyring()
        store = CredentialStore(backend=backend)
        repository = self.repository()
        token = "test-private-token"

        store.set_token(token)

        self.assertTrue(store.has_token())
        self.assertEqual(store.token(), token)
        serialized_settings = "\n".join(
            f"{key}={repository.settings.value(key)}"
            for key in repository.settings.allKeys()
        )
        self.assertNotIn(token, serialized_settings)
        store.clear_token()
        self.assertFalse(store.has_token())

    def test_diagnostic_logs_redact_private_paths(self):
        paths = self.repository().paths
        store = DiagnosticLogStore(paths)
        store.write("error", f"Failed at {paths.input_root / 'private.txt'}")
        content = store.path.read_text(encoding="utf-8")

        self.assertNotIn(str(self.project), content)
        self.assertIn("<library>", content)


if __name__ == "__main__":
    unittest.main()
