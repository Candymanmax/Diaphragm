from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from modules.app_settings import SettingsRepository
from modules.config import PipelineConfig
from modules.events import emit_event
from modules.jobs import JobStoreError
from modules.service import JobRequest, TTSHarnessService


class HarnessServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.script = self.root / "input" / "script.txt"
        self.voice = self.root / "voices" / "voice.wav"
        self.script.parent.mkdir(parents=True)
        self.voice.parent.mkdir(parents=True)
        self.script.write_text("A service layer test.", encoding="utf-8")
        self.voice.write_bytes(b"voice")
        (self.root / "config.default.yaml").write_text(
            "voice: voice.wav\nmodel: original\nlanguage: en\n",
            encoding="utf-8",
        )
        self.settings_repository = SettingsRepository.for_testing(self.root)

    def test_create_job_uses_typed_request_and_private_copies(self):
        service = TTSHarnessService(self.settings_repository.paths)
        manifest = service.create_job(JobRequest(
            scripts=(str(self.script),),
        ))

        self.assertEqual(manifest["status"], "pending")
        self.assertTrue(
            service.store.resolve_artifact(
                manifest["job_id"],
                manifest["scripts"][0]["source_path"],
            ).is_file()
        )
        self.assertTrue((self.root / "config.yaml").is_file())

    def test_create_job_can_use_job_settings_without_saving_defaults(self):
        service = TTSHarnessService(self.settings_repository.paths)
        override = PipelineConfig(
            voice="voice.wav",
            model="nano",
        )

        manifest = service.create_job(
            JobRequest(scripts=(str(self.script),)),
            config_override=override,
        )

        self.assertEqual(manifest["settings"]["model"], "nano")
        self.assertEqual(service.load_config().model, "original")

    def test_service_converts_runner_output_to_structured_events(self):
        events = []

        def runner(store, manifest, event_callback=None):
            print("ordinary pipeline output")
            emit_event(
                event_callback,
                "job.completed",
                "done",
                job_id=manifest["job_id"],
            )
            return 0

        service = TTSHarnessService(self.settings_repository.paths, runner=runner)
        manifest = service.create_job(JobRequest(
            scripts=(str(self.script),),
        ))
        result = service.run_manifest(manifest, event_callback=events.append)

        self.assertEqual(result, 0)
        self.assertIn("log", [event.kind for event in events])
        self.assertIn("job.completed", [event.kind for event in events])

    def test_retained_segment_text_can_be_edited_and_reset(self):
        service = TTSHarnessService(self.settings_repository.paths)
        settings = asdict(PipelineConfig(
            voice="voice.wav",
            retain_job_artifacts=True,
        ))
        manifest = service.store.create_job(
            scripts=(self.script,),
            settings=settings,
            voice_file=self.voice,
            job_id="retained-segments",
        )
        script = manifest["scripts"][0]
        text_path = service.store.resolve_artifact(
            manifest["job_id"],
            Path(script["chunks_directory"]) / "chunk0001.txt",
        )
        audio_path = service.store.resolve_artifact(
            manifest["job_id"],
            Path(script["audio_directory"]) / "chunk0001.wav",
        )
        text_path.parent.mkdir(parents=True)
        audio_path.parent.mkdir(parents=True)
        text_path.write_text("Old segment text.", encoding="utf-8")
        audio_path.write_bytes(b"audio")
        script["chunks"] = [{
            "id": "chunk0001",
            "text_path": service.store.artifact_relative(
                manifest["job_id"], text_path
            ),
            "audio_path": service.store.artifact_relative(
                manifest["job_id"], audio_path
            ),
            "status": "complete",
            "attempts": 1,
            "error": None,
            "started_at": None,
            "completed_at": None,
            "elapsed_seconds": 1.0,
        }]
        script["status"] = "complete"
        manifest["status"] = "complete"
        service.store.save(manifest)

        changed = service.update_chunk_text(
            manifest["job_id"],
            script["id"],
            "chunk0001",
            "New segment text.",
        )

        self.assertEqual(text_path.read_text(encoding="utf-8").strip(), "New segment text.")
        self.assertFalse(audio_path.exists())
        self.assertEqual(changed["status"], "pending")
        self.assertEqual(changed["scripts"][0]["chunks"][0]["status"], "pending")

    def test_non_retained_job_rejects_segment_regeneration(self):
        service = TTSHarnessService(self.settings_repository.paths)
        manifest = service.create_job(JobRequest(
            scripts=(str(self.script),),
        ))

        with self.assertRaisesRegex(JobStoreError, "Keep segment files"):
            service.reset_chunks(
                manifest["job_id"],
                manifest["scripts"][0]["id"],
                ("chunk0001",),
            )


if __name__ == "__main__":
    unittest.main()

