from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock

from modules.config import PipelineConfig
from modules.jobs import JobControlRequested, JobStore
from modules.pipeline.chunks import generate_pending_chunks


class PipelineCancellationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name)
        self.store = JobStore(self.workspace / "jobs")
        script_file = self.workspace / "script.txt"
        voice_file = self.workspace / "voice.wav"
        script_file.write_text("A cancellation test.", encoding="utf-8")
        voice_file.write_bytes(b"voice")
        self.manifest = self.store.create_job(
            scripts=[script_file],
            settings=asdict(PipelineConfig(voice="voice.wav")),
            voice_file=voice_file,
            job_id="cancellation-test",
        )
        self.manifest["status"] = "running"
        script = self.manifest["scripts"][0]
        script["status"] = "running"
        chunks_folder = self.store.resolve_artifact(
            self.manifest["job_id"],
            script["chunks_directory"],
        )
        chunks_folder.mkdir(parents=True)
        chunk_file = chunks_folder / "chunk0001.txt"
        chunk_file.write_text("A pending chunk.", encoding="utf-8")
        script["chunks"] = [{
            "id": "chunk0001",
            "text_path": self.store.artifact_relative(
                self.manifest["job_id"],
                chunk_file,
            ),
            "audio_path": (
                Path(script["audio_directory"]) / "chunk0001.wav"
            ).as_posix(),
            "status": "pending",
            "attempts": 0,
            "error": None,
            "started_at": None,
            "completed_at": None,
            "elapsed_seconds": None,
        }]
        self.store.save(self.manifest)

    def test_cancel_is_checked_before_model_loading(self):
        self.store.request_cancel(self.manifest["job_id"])
        provider = Mock()

        with self.assertRaises(JobControlRequested) as raised:
            generate_pending_chunks(
                self.store,
                self.manifest,
                self.manifest["scripts"][0],
                None,
                provider,
            )

        self.assertEqual(raised.exception.action, "cancel")
        provider.assert_not_called()
        self.assertEqual(
            self.store.load(self.manifest["job_id"])["status"],
            "cancelled",
        )

    def test_cancel_during_model_loading_is_checked_before_generation(self):
        generator = Mock()

        def provider(*args):
            del args
            self.store.request_cancel(self.manifest["job_id"])
            return generator

        with self.assertRaises(JobControlRequested) as raised:
            generate_pending_chunks(
                self.store,
                self.manifest,
                self.manifest["scripts"][0],
                None,
                provider,
            )

        self.assertEqual(raised.exception.action, "cancel")
        generator.run.assert_not_called()
        self.assertEqual(
            self.store.load(self.manifest["job_id"])["status"],
            "cancelled",
        )


if __name__ == "__main__":
    unittest.main()
