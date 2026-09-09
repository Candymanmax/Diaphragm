from dataclasses import asdict
from pathlib import Path
import queue
from tempfile import TemporaryDirectory
import time
import unittest

from modules.app_settings import SettingsRepository
from modules.config import PipelineConfig
from modules.events import HarnessEvent
from modules.service import TTSHarnessService
from modules.worker import JobWorkerProcess


class WorkerProcessTests(unittest.TestCase):
    @staticmethod
    def _collect_until_stopped(worker, timeout=60):
        process = worker.process
        events = []

        if process is None:
            return events

        process.join(timeout)
        if process.is_alive():
            return events

        queue_deadline = time.monotonic() + 2
        while time.monotonic() < queue_deadline:
            remaining = queue_deadline - time.monotonic()
            try:
                value = worker.event_queue.get(timeout=remaining)
            except (EOFError, OSError, queue.Empty):
                break

            try:
                event = HarnessEvent.from_dict(value)
            except ValueError:
                continue

            events.append(event)
            if event.kind in {"worker.finished", "worker.crashed"}:
                break

        events.extend(worker.poll(limit=1000))

        return events

    @staticmethod
    def _create_job(root, job_id, *, retain_job_artifacts=False):
        source = root / "input" / "script.txt"
        voice = root / "voices" / "voice.wav"
        source.parent.mkdir(parents=True)
        voice.parent.mkdir(parents=True)
        source.write_text(f"{job_id} test.", encoding="utf-8")
        voice.write_bytes(b"voice")
        paths = SettingsRepository.for_testing(root).paths
        service = TTSHarnessService(paths)
        settings = asdict(
            PipelineConfig(
                voice="voice.wav",
                retain_job_artifacts=retain_job_artifacts,
            )
        )
        manifest = service.store.create_job(
            scripts=(source,),
            settings=settings,
            voice_file=voice,
            job_id=job_id,
        )
        return paths, service, manifest

    def test_worker_runs_outside_the_caller_and_streams_terminal_event(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths, service, manifest = self._create_job(
                root,
                "worker-isolation",
                retain_job_artifacts=True,
            )
            manifest["status"] = "complete"
            service.store.save(manifest)
            worker = JobWorkerProcess(paths)
            events = []

            try:
                worker.start(manifest["job_id"], mode="prepared")
                events.extend(self._collect_until_stopped(worker))

                self.assertFalse(worker.running, "worker did not stop")
                self.assertEqual(worker.exit_code(), 0)

                kinds = [event.kind for event in events]
                self.assertIn("worker.started", kinds)
                self.assertIn("job.completed", kinds)
                self.assertIn("worker.finished", kinds)
                terminal = next(
                    event for event in events
                    if event.kind == "worker.finished"
                )
                self.assertEqual(terminal.payload["return_code"], 0)
            finally:
                worker.terminate()
                worker.close()

    def test_worker_crash_has_nonzero_process_status_and_event(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths, service, manifest = self._create_job(
                root,
                "worker-crash",
            )
            copied_voice = service.store.resolve_artifact(
                manifest["job_id"],
                manifest["voice"]["path"],
            )
            copied_voice.unlink()
            worker = JobWorkerProcess(paths)

            try:
                worker.start(manifest["job_id"], mode="prepared")
                events = self._collect_until_stopped(worker)

                self.assertFalse(worker.running, "worker did not stop")
                self.assertNotEqual(worker.exit_code(), 0)
                self.assertIn(
                    "worker.crashed",
                    [event.kind for event in events],
                )
            finally:
                worker.terminate()
                worker.close()

    def test_start_rejects_an_unknown_mode_without_spawning(self):
        with TemporaryDirectory() as temporary:
            paths = SettingsRepository.for_testing(Path(temporary)).paths
            worker = JobWorkerProcess(paths)

            with self.assertRaisesRegex(ValueError, "Unknown worker mode"):
                worker.start("job-id", mode="unsupported")

            self.assertIsNone(worker.process)
            self.assertIsNone(worker.event_queue)

    def test_poll_decodes_events_and_ignores_malformed_queue_values(self):
        with TemporaryDirectory() as temporary:
            paths = SettingsRepository.for_testing(Path(temporary)).paths
            worker = JobWorkerProcess(paths)
            event_queue = queue.Queue()
            event_queue.put(HarnessEvent(kind="worker.started").to_dict())
            event_queue.put({"schema_version": 999, "kind": "invalid"})
            event_queue.put("not an event")
            worker.event_queue = event_queue

            try:
                events = worker.poll(limit=10)
            finally:
                worker.event_queue = None

            self.assertEqual(
                [event.kind for event in events],
                ["worker.started"],
            )


if __name__ == "__main__":
    unittest.main()
