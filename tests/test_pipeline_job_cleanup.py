from contextlib import redirect_stderr, redirect_stdout
from dataclasses import asdict
import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from modules.app_settings import AppPaths
from modules.config import PipelineConfig
from modules.jobs import JobStore
from modules.pipeline import run_job


class PipelineJobCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.workspace = Path(self.temporary.name)
        self.paths = AppPaths(
            install_root=self.workspace,
            data_root=self.workspace,
            library_root=self.workspace,
            model_cache_root=self.workspace / "models",
            defaults_file=self.workspace / "config.default.yaml",
            config_file=self.workspace / "config.yaml",
            logs_root=self.workspace / "logs",
        )
        self.store = JobStore(self.workspace / "jobs")
        script = self.workspace / "script.txt"
        voice = self.workspace / "voice.wav"
        script.write_text("A pipeline cleanup test.", encoding="utf-8")
        voice.write_bytes(b"voice")
        self.manifest = self.store.create_job(
            scripts=[script],
            settings=asdict(PipelineConfig(voice="voice.wav")),
            voice_file=voice,
            job_id="pipeline-cleanup-test",
        )

    def _create_intermediate_artifacts(self, script):
        job_id = self.manifest["job_id"]

        for key, filename, contents in (
            ("chunks_directory", "chunk0001.txt", b"chunk text"),
            ("audio_directory", "chunk0001.wav", b"chunk audio"),
            ("work_directory", "merged.wav", b"merged audio"),
        ):
            folder = self.store.resolve_artifact(job_id, script[key])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / filename).write_bytes(contents)

    def test_successful_run_removes_intermediate_chunk_artifacts(self):
        script = self.manifest["scripts"][0]

        def complete_script(
            store,
            manifest,
            script_entry,
            config,
            voice,
            generator_provider,
        ):
            self._create_intermediate_artifacts(script_entry)
            output = store.resolve_artifact(
                manifest["job_id"],
                script_entry["output_path"],
            )
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"final audio")
            script_entry["status"] = "complete"
            store.save(manifest)

        with (
            patch(
                "modules.pipeline.job_runner.process_job_script",
                side_effect=complete_script,
            ),
            redirect_stdout(io.StringIO()),
        ):
            return_code = run_job(
                self.store,
                self.manifest,
                app_paths=self.paths,
            )

        completed = self.store.load(self.manifest["job_id"])
        completed_script = completed["scripts"][0]

        self.assertEqual(return_code, 0)
        self.assertEqual(completed["status"], "complete")
        self.assertEqual(
            completed["artifact_cleanup"]["status"],
            "complete",
        )

        for key in (
            "chunks_directory",
            "audio_directory",
            "work_directory",
        ):
            self.assertFalse(
                self.store.resolve_artifact(
                    completed["job_id"],
                    completed_script[key],
                ).exists()
            )

        self.assertTrue(
            self.store.resolve_artifact(
                completed["job_id"],
                completed_script["source_path"],
            ).is_file()
        )
        self.assertTrue(
            self.store.resolve_artifact(
                completed["job_id"],
                completed_script["output_path"],
            ).is_file()
        )

    def test_failed_run_keeps_intermediate_chunk_artifacts(self):
        script = self.manifest["scripts"][0]

        def fail_script(
            store,
            manifest,
            script_entry,
            config,
            voice,
            generator_provider,
        ):
            self._create_intermediate_artifacts(script_entry)
            raise RuntimeError("planned failure")

        with (
            patch(
                "modules.pipeline.job_runner.process_job_script",
                side_effect=fail_script,
            ),
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()),
        ):
            return_code = run_job(
                self.store,
                self.manifest,
                app_paths=self.paths,
            )

        failed = self.store.load(self.manifest["job_id"])
        failed_script = failed["scripts"][0]

        self.assertEqual(return_code, 1)
        self.assertEqual(failed["status"], "failed")

        for key in (
            "chunks_directory",
            "audio_directory",
            "work_directory",
        ):
            self.assertTrue(
                self.store.resolve_artifact(
                    failed["job_id"],
                    failed_script[key],
                ).is_dir()
            )

    def test_successful_review_job_retains_segment_artifacts(self):
        source = self.workspace / "review-script.txt"
        voice = self.workspace / "voice.wav"
        source.write_text("A retained review test.", encoding="utf-8")
        manifest = self.store.create_job(
            scripts=[source],
            settings=asdict(PipelineConfig(
                voice="voice.wav",
                retain_job_artifacts=True,
            )),
            voice_file=voice,
            job_id="review-artifacts-test",
        )

        def complete_script(
            store,
            job_manifest,
            script_entry,
            config,
            voice_file,
            generator_provider,
        ):
            del config, voice_file, generator_provider

            for key, filename in (
                ("chunks_directory", "chunk0001.txt"),
                ("audio_directory", "chunk0001.wav"),
                ("work_directory", "merged.wav"),
            ):
                folder = store.resolve_artifact(
                    job_manifest["job_id"],
                    script_entry[key],
                )
                folder.mkdir(parents=True, exist_ok=True)
                (folder / filename).write_bytes(b"retained")

            output = store.resolve_artifact(
                job_manifest["job_id"],
                script_entry["output_path"],
            )
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"final")
            script_entry["status"] = "complete"
            store.save(job_manifest)

        with (
            patch(
                "modules.pipeline.job_runner.process_job_script",
                side_effect=complete_script,
            ),
            redirect_stdout(io.StringIO()),
        ):
            return_code = run_job(
                self.store,
                manifest,
                app_paths=self.paths,
            )

        completed = self.store.load(manifest["job_id"])
        script = completed["scripts"][0]
        self.assertEqual(return_code, 0)
        self.assertEqual(
            completed["artifact_cleanup"]["status"],
            "retained",
        )

        for key in (
            "chunks_directory",
            "audio_directory",
            "work_directory",
        ):
            self.assertTrue(
                self.store.resolve_artifact(
                    completed["job_id"],
                    script[key],
                ).is_dir()
            )

    def test_one_loaded_model_session_is_reused_across_scripts(self):
        second_script = self.workspace / "second-script.txt"
        voice = self.workspace / "voice.wav"
        second_script.write_text("A second script.", encoding="utf-8")
        first_source = self.workspace / "first-script.txt"
        first_source.write_text("A first script.", encoding="utf-8")
        manifest = self.store.create_job(
            scripts=[first_source, second_script],
            settings=asdict(PipelineConfig(voice="voice.wav")),
            voice_file=voice,
            job_id="shared-model-test",
        )
        sessions = []

        class FakeGenerator:
            instances = 0
            unloads = 0

            def __init__(self, **kwargs):
                FakeGenerator.instances += 1

            def runtime_report(self):
                return {
                    "device": "cpu",
                    "current_section_words": 80,
                }

            def runtime_summary(self):
                return "CPU | section 80 words"

            def unload(self):
                FakeGenerator.unloads += 1

        def process_script(
            store,
            job_manifest,
            script_entry,
            config,
            voice_file,
            generator_provider,
        ):
            chunks = store.resolve_artifact(
                job_manifest["job_id"],
                script_entry["chunks_directory"],
            )
            audio = store.resolve_artifact(
                job_manifest["job_id"],
                script_entry["audio_directory"],
            )
            sessions.append(generator_provider(chunks, audio))
            script_entry["status"] = "complete"
            store.save(job_manifest)

        with (
            patch(
                "modules.pipeline.generator_session.VoiceGenerator",
                FakeGenerator,
            ),
            patch(
                "modules.pipeline.job_runner.process_job_script",
                side_effect=process_script,
            ),
            redirect_stdout(io.StringIO()),
        ):
            return_code = run_job(
                self.store,
                manifest,
                app_paths=self.paths,
            )

        self.assertEqual(return_code, 0)
        self.assertEqual(FakeGenerator.instances, 1)
        self.assertEqual(FakeGenerator.unloads, 1)
        self.assertEqual(len(sessions), 2)
        self.assertIs(sessions[0], sessions[1])


if __name__ == "__main__":
    unittest.main()
