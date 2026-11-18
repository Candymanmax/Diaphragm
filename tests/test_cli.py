from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, PropertyMock, patch

import diaphragm
from modules.app_settings import SettingsRepository
from modules.events import HarnessEvent


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def test_help_works_without_runtime_dependencies(self):
        result = subprocess.run(
            [sys.executable, "-S", "-m", "diaphragm", "generate", "--help"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertIn("--voice VOICE.wav", result.stdout)

    def test_generate_reports_output_paths_in_desktop_library(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            repository = SettingsRepository.for_testing(
                root, defaults_file=PROJECT_ROOT / "config.default.yaml"
            )
            script = root / "test script.txt"
            voice = root / "test voice.wav"
            script.write_text("A short test.", encoding="utf-8")
            voice.write_bytes(b"test voice")

            def finish_job(service, job_id, *, mode):
                self.assertEqual(mode, "prepared")
                manifest = service.load_job(job_id)
                output = service.paths.library_root / manifest["scripts"][0]["published_output"]
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(b"test output")
                manifest["status"] = "complete"
                service.store.save(manifest)
                return 0

            stdout, stderr = StringIO(), StringIO()
            with (
                patch.object(
                    SettingsRepository, "for_application", return_value=repository
                ),
                patch.object(diaphragm, "_run_worker", side_effect=finish_job),
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                exit_code = diaphragm.main(
                    ["generate", str(script), "--voice", str(voice)]
                )

            self.assertEqual(exit_code, 0)
            [manifest_path] = repository.paths.jobs_root.glob("*/manifest.json")
            self.assertEqual(
                stdout.getvalue().splitlines(),
                [str(root / "final" / "cli" / manifest_path.parent.name / "test-script.wav")],
            )
            self.assertIn("Created job ", stderr.getvalue())

    def test_jobs_list_show_and_resume_use_the_saved_job(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            repository = SettingsRepository.for_testing(
                root, defaults_file=PROJECT_ROOT / "config.default.yaml"
            )
            script = root / "chapter.txt"
            voice = root / "voice.wav"
            script.write_text("A short test.", encoding="utf-8")
            voice.write_bytes(b"test voice")

            def pause_job(service, job_id, *, mode):
                manifest = service.load_job(job_id)
                manifest["status"] = "paused"
                service.store.save(manifest)
                return 75

            def resume_job(service, job_id, *, mode):
                self.assertEqual(mode, "resume")
                manifest = service.prepare_job(job_id)
                self.assertEqual(manifest["status"], "pending")
                output = root / "final" / "cli" / job_id / "chapter.wav"
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(b"test output")
                manifest["status"] = "complete"
                service.store.save(manifest)
                return 0

            with patch.object(
                SettingsRepository, "for_application", return_value=repository
            ):
                with (
                    patch.object(diaphragm, "_run_worker", side_effect=pause_job) as worker,
                    redirect_stderr(StringIO()),
                ):
                    self.assertEqual(
                        diaphragm.main(["generate", str(script), "--voice", str(voice)]),
                        75,
                    )
                    _, job_id = worker.call_args.args

                stdout = StringIO()
                with redirect_stdout(stdout):
                    self.assertEqual(diaphragm.main(["jobs", "list"]), 0)
                    self.assertEqual(diaphragm.main(["jobs", "show", job_id]), 0)
                self.assertIn(f"{job_id}\tpaused\tchapter.txt", stdout.getvalue())
                self.assertIn(f"Job {job_id} (paused)", stdout.getvalue())

                stdout = StringIO()
                with (
                    patch.object(diaphragm, "_run_worker", side_effect=resume_job),
                    redirect_stdout(stdout),
                    redirect_stderr(StringIO()),
                ):
                    self.assertEqual(diaphragm.main(["jobs", "resume", job_id]), 0)
                self.assertEqual(
                    stdout.getvalue().splitlines(),
                    [str(root / "final" / "cli" / job_id / "chapter.wav")],
                )

    def test_ctrl_c_before_resume_preparation_waits_to_send_pause(self):
        service = Mock()
        worker = Mock()
        worker.start.side_effect = lambda *args, **kwargs: signal.raise_signal(signal.SIGINT)
        worker.poll.side_effect = [
            [HarnessEvent(kind="worker.started")],
            [HarnessEvent(kind="job.started")],
            [],
        ]
        worker.exit_code.return_value = 75

        def running():
            service.request_pause.assert_not_called()
            yield True
            service.request_pause.assert_not_called()
            yield True
            service.request_pause.assert_called_once_with("example-job")
            yield False

        with (
            patch("modules.worker.JobWorkerProcess", return_value=worker),
            patch.object(
                type(worker), "running", create=True, new_callable=PropertyMock,
                side_effect=running(),
            ),
            redirect_stderr(StringIO()),
        ):
            handler = signal.getsignal(signal.SIGINT)
            self.assertEqual(diaphragm._run_worker(service, "example-job", mode="resume"), 75)
            self.assertIs(signal.getsignal(signal.SIGINT), handler)
        worker.start.assert_called_once_with("example-job", mode="resume", terminal=True)
