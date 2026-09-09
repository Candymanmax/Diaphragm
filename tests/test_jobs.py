from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from modules.jobs import JobStore, JobStoreError


class PersistentJobStoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name)
        self.store = JobStore(self.workspace / "jobs")
        self.script = self.workspace / "private-script.txt"
        self.script.write_text(
            "This is a private test script.",
            encoding="utf-8",
        )
        self.voice = self.workspace / "private-voice.wav"
        self.voice.write_bytes(b"RIFF-fake-voice")
        self.settings = {
            "voice": str(self.voice),
            "model": "original",
            "language": "en",
            "output_format": "wav",
            "merge_audio": True,
        }

    def _create_job(self, job_id="test-job"):
        return self.store.create_job(
            scripts=[self.script],
            settings=self.settings,
            voice_file=self.voice,
            job_id=job_id,
        )

    def _add_chunks(self, manifest):
        script = manifest["scripts"][0]
        chunks_folder = self.store.resolve_artifact(
            manifest["job_id"],
            script["chunks_directory"],
        )
        audio_folder = self.store.resolve_artifact(
            manifest["job_id"],
            script["audio_directory"],
        )
        chunks_folder.mkdir(parents=True)
        audio_folder.mkdir(parents=True)
        entries = []

        for number in (1, 2):
            stem = f"chunk{number:04d}"
            text_file = chunks_folder / f"{stem}.txt"
            audio_file = audio_folder / f"{stem}.wav"
            text_file.write_text(f"Chunk {number}.", encoding="utf-8")
            entries.append({
                "id": stem,
                "text_path": self.store.artifact_relative(
                    manifest["job_id"],
                    text_file,
                ),
                "audio_path": self.store.artifact_relative(
                    manifest["job_id"],
                    audio_file,
                ),
                "status": "pending",
                "attempts": 0,
                "error": None,
                "started_at": None,
                "completed_at": None,
                "elapsed_seconds": None,
            })

        script["chunks"] = entries
        self.store.save(manifest)
        return script, entries, audio_folder

    def test_new_job_has_an_isolated_manifest_and_private_copies(self):
        manifest = self._create_job()
        job_folder = self.store.job_folder("test-job")
        loaded = self.store.load("test-job")

        self.assertEqual(loaded["status"], "pending")
        self.assertEqual(loaded["settings"]["voice"], "voice/reference.wav")
        self.assertEqual(
            self.store.resolve_artifact(
                "test-job",
                loaded["scripts"][0]["source_path"],
            ).read_text(encoding="utf-8"),
            self.script.read_text(encoding="utf-8"),
        )
        self.assertEqual(
            self.store.resolve_artifact(
                "test-job",
                loaded["voice"]["path"],
            ).read_bytes(),
            self.voice.read_bytes(),
        )
        self.assertFalse(
            any(path.name.endswith(".tmp") for path in job_folder.rglob("*"))
        )
        self.assertEqual(manifest["job_id"], "test-job")

        manifest_text = json.dumps(loaded)
        self.assertNotIn(str(self.workspace), manifest_text)

    def test_generated_job_ids_are_unique_and_safe(self):
        first = self.store.new_job_id()
        second = self.store.new_job_id()

        self.assertNotEqual(first, second)
        self.assertEqual(self.store.validate_job_id(first), first)

        with self.assertRaises(JobStoreError):
            self.store.validate_job_id("../outside")

        with self.assertRaises(JobStoreError):
            self.store.resolve_artifact(first, "../../outside.txt")

    def test_draft_manifest_is_persisted_without_staging_generation_files(self):
        manifest = self.store.create_draft("Draft narration")
        folder = self.store.job_folder(manifest["job_id"])

        self.assertTrue(manifest["temporary"])
        self.assertEqual(self.store.load(manifest["job_id"]), manifest)
        self.assertEqual(
            [job["job_id"] for job in self.store.list_jobs()],
            [manifest["job_id"]],
        )
        self.assertTrue((folder / "manifest.json").is_file())
        self.assertEqual(
            {path.name for path in folder.iterdir()},
            {"manifest.json"},
        )

    def test_discarding_a_draft_removes_only_its_manifest_folder(self):
        manifest = self.store.create_draft("Discardable draft")
        folder = self.store.job_folder(manifest["job_id"])

        discarded = self.store.delete_draft(manifest["job_id"])

        self.assertEqual(discarded["job_id"], manifest["job_id"])
        self.assertFalse(folder.exists())
        self.assertEqual(self.store.list_jobs(), [])

    def test_persistent_jobs_cannot_be_discarded_as_drafts(self):
        manifest = self._create_job()

        with self.assertRaisesRegex(JobStoreError, "Only draft jobs"):
            self.store.delete_draft(manifest["job_id"])

        self.assertTrue(self.store.job_folder(manifest["job_id"]).is_dir())

    def test_running_chunks_recover_from_atomic_audio_files(self):
        manifest = self._create_job()
        script, chunks, audio_folder = self._add_chunks(manifest)
        chunks[0]["status"] = "running"
        chunks[1]["status"] = "running"
        (audio_folder / "chunk0001.wav").write_bytes(b"complete audio")
        script["status"] = "running"
        manifest["status"] = "running"
        self.store.save(manifest)

        recovered = self.store.recover(self.store.load("test-job"))

        self.assertEqual(recovered["status"], "interrupted")
        self.assertEqual(recovered["scripts"][0]["status"], "pending")
        self.assertEqual(
            [chunk["status"] for chunk in recovered["scripts"][0]["chunks"]],
            ["complete", "pending"],
        )

    def test_pause_and_cancel_requests_use_durable_markers(self):
        self._create_job()

        self.store.request_pause("test-job")
        self.assertEqual(self.store.control_action("test-job"), "pause")

        self.store.request_cancel("test-job")
        self.assertEqual(self.store.control_action("test-job"), "cancel")
        self.assertEqual(self.store.load("test-job")["status"], "cancelled")

        self.store.clear_controls("test-job")
        self.assertIsNone(self.store.control_action("test-job"))

    def test_failed_manifest_replacement_keeps_last_valid_json(self):
        self._create_job()
        invalid = self.store.load("test-job")
        invalid["not_json_serializable"] = {"a set"}

        with self.assertRaises(TypeError):
            self.store.save(invalid)

        recovered = self.store.load("test-job")
        self.assertNotIn("not_json_serializable", recovered)
        self.assertFalse(
            any(
                path.name.endswith(".tmp")
                for path in self.store.job_folder("test-job").iterdir()
            )
        )

    def test_retry_failed_preserves_complete_chunks(self):
        manifest = self._create_job()
        script, chunks, audio_folder = self._add_chunks(manifest)
        complete_audio = audio_folder / "chunk0001.wav"
        failed_audio = audio_folder / "chunk0002.wav"
        complete_audio.write_bytes(b"complete")
        failed_audio.write_bytes(b"failed partial")
        chunks[0]["status"] = "complete"
        chunks[1]["status"] = "failed"
        chunks[1]["attempts"] = 2
        chunks[1]["error"] = "mock error"
        script["status"] = "failed"
        manifest["status"] = "failed"
        self.store.save(manifest)

        retried = self.store.prepare_for_resume(
            "test-job",
            retry_failed=True,
        )

        retried_chunks = retried["scripts"][0]["chunks"]
        self.assertEqual(retried_chunks[0]["status"], "complete")
        self.assertEqual(retried_chunks[1]["status"], "pending")
        self.assertEqual(retried_chunks[1]["attempts"], 2)
        self.assertTrue(complete_audio.is_file())
        self.assertFalse(failed_audio.exists())
        self.assertEqual(retried["status"], "pending")

    def test_restart_resets_all_chunks_but_keeps_source_and_text(self):
        manifest = self._create_job()
        script, chunks, audio_folder = self._add_chunks(manifest)
        source = self.store.resolve_artifact(
            "test-job",
            script["source_path"],
        )
        chunk_text = self.store.resolve_artifact(
            "test-job",
            chunks[0]["text_path"],
        )
        (audio_folder / "chunk0001.wav").write_bytes(b"audio")
        chunks[0]["status"] = "complete"
        chunks[0]["attempts"] = 3
        script["status"] = "complete"
        manifest["status"] = "complete"
        self.store.save(manifest)

        restarted = self.store.prepare_for_resume(
            "test-job",
            restart=True,
        )

        restarted_chunk = restarted["scripts"][0]["chunks"][0]
        self.assertEqual(restarted["status"], "pending")
        self.assertEqual(restarted_chunk["status"], "pending")
        self.assertEqual(restarted_chunk["attempts"], 0)
        self.assertTrue(source.is_file())
        self.assertTrue(chunk_text.is_file())
        self.assertFalse(audio_folder.exists())

    def test_completed_job_deletes_chunks_but_keeps_restart_sources_and_output(self):
        manifest = self._create_job()
        script, chunks, audio_folder = self._add_chunks(manifest)
        job_id = manifest["job_id"]
        chunks_folder = self.store.resolve_artifact(
            job_id,
            script["chunks_directory"],
        )
        work_folder = self.store.resolve_artifact(
            job_id,
            script["work_directory"],
        )
        output_file = self.store.resolve_artifact(
            job_id,
            script["output_path"],
        )
        source_file = self.store.resolve_artifact(
            job_id,
            script["source_path"],
        )
        voice_file = self.store.resolve_artifact(
            job_id,
            manifest["voice"]["path"],
        )
        work_folder.mkdir(parents=True)
        output_file.parent.mkdir(parents=True)
        (work_folder / "merged.wav").write_bytes(b"merged")
        output_file.write_bytes(b"final output")

        for chunk in chunks:
            chunk["status"] = "complete"
            self.store.resolve_artifact(
                job_id,
                chunk["audio_path"],
            ).write_bytes(b"chunk audio")

        script["status"] = "complete"
        manifest["status"] = "complete"
        self.store.save(manifest)

        cleaned = self.store.cleanup_completed_artifacts(manifest)

        self.assertFalse(chunks_folder.exists())
        self.assertFalse(audio_folder.exists())
        self.assertFalse(work_folder.exists())
        self.assertTrue(source_file.is_file())
        self.assertTrue(voice_file.is_file())
        self.assertTrue(output_file.is_file())
        self.assertEqual(
            cleaned["artifact_cleanup"]["status"],
            "complete",
        )
        self.assertTrue(script["artifacts_cleaned_at"])
        self.assertTrue(
            all(chunk["status"] == "complete" for chunk in chunks)
        )

        self.store.cleanup_completed_artifacts(cleaned)

    def test_incomplete_job_refuses_destructive_chunk_cleanup(self):
        manifest = self._create_job()
        script, _, _ = self._add_chunks(manifest)
        chunks_folder = self.store.resolve_artifact(
            manifest["job_id"],
            script["chunks_directory"],
        )

        with self.assertRaisesRegex(JobStoreError, "completed job"):
            self.store.cleanup_completed_artifacts(manifest)

        self.assertTrue(chunks_folder.is_dir())


if __name__ == "__main__":
    unittest.main()
