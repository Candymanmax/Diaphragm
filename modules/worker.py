from __future__ import annotations

import multiprocessing
import queue
import traceback

from modules.runtime_manager import activate_runtime_imports

# A frozen worker starts in a fresh interpreter.  Re-apply the per-user
# runtime's import and DLL paths before importing any service that can load
# the speech-generation pipeline.  Source launches simply no-op here because
# their active virtual environment is already on sys.path.
activate_runtime_imports()

from modules.app_settings import AppPaths
from modules.events import HarnessEvent, emit_event
from modules.service import TTSHarnessService


def _queue_callback(event_queue):
    def callback(event):
        try:
            event_queue.put(event.to_dict())
        except (BrokenPipeError, EOFError, OSError):
            pass

    return callback


def run_job_worker(
    app_paths,
    job_id,
    mode,
    event_queue,
):
    callback = _queue_callback(event_queue)
    emit_event(
        callback,
        "worker.started",
        "Generation worker started",
        job_id=job_id,
        payload={"mode": mode},
    )

    try:
        service = TTSHarnessService(app_paths)
        return_code = service.run_job(
            job_id,
            retry_failed=mode == "retry",
            restart=mode == "restart",
            prepared=mode == "prepared",
            event_callback=callback,
        )
        emit_event(
            callback,
            "worker.finished",
            "Generation worker finished",
            job_id=job_id,
            payload={"return_code": int(return_code)},
        )
    except BaseException as error:
        emit_event(
            callback,
            "worker.crashed",
            f"{type(error).__name__}: {error}",
            job_id=job_id,
            payload={"traceback": traceback.format_exc()},
        )
        raise SystemExit(1) from None

    # Make the OS process status a reliable fallback if the final queue event
    # is still flushing when the GUI observes process completion.
    if return_code:
        raise SystemExit(int(return_code))


class JobWorkerProcess:
    """Spawn-isolated model process with a structured event queue."""

    def __init__(self, app_paths):
        self.paths = (
            app_paths
            if isinstance(app_paths, AppPaths)
            else AppPaths.from_dict(app_paths)
        )
        self.context = multiprocessing.get_context("spawn")
        self.event_queue = None
        self.process = None
        self.job_id = None

    @property
    def running(self):
        return self.process is not None and self.process.is_alive()

    def start(self, job_id, mode="resume"):
        if self.running:
            raise RuntimeError("A generation worker is already running")

        if mode not in {"prepared", "resume", "retry", "restart"}:
            raise ValueError(f"Unknown worker mode: {mode}")

        self.close()
        self.job_id = str(job_id)
        self.event_queue = self.context.Queue()
        self.process = self.context.Process(
            target=run_job_worker,
            args=(
                self.paths.to_dict(),
                self.job_id,
                mode,
                self.event_queue,
            ),
            name=f"tts-job-{self.job_id}",
            daemon=True,
        )
        self.process.start()

    def poll(self, limit=200):
        events = []

        if self.event_queue is None:
            return events

        for _ in range(max(1, int(limit))):
            try:
                value = self.event_queue.get_nowait()
            except queue.Empty:
                break
            except (EOFError, OSError):
                break

            try:
                events.append(HarnessEvent.from_dict(value))
            except ValueError:
                continue

        return events

    def exit_code(self):
        if self.process is None or self.process.is_alive():
            return None

        return self.process.exitcode

    def terminate(self):
        if self.process is None or not self.process.is_alive():
            return

        self.process.terminate()
        self.process.join(timeout=5)

        if self.process.is_alive() and hasattr(self.process, "kill"):
            self.process.kill()
            self.process.join(timeout=2)

    def close(self):
        if self.process is not None and not self.process.is_alive():
            self.process.join(timeout=0.1)

        if self.event_queue is not None:
            try:
                self.event_queue.close()
                self.event_queue.cancel_join_thread()
            except (OSError, ValueError):
                pass

        self.process = None
        self.event_queue = None
        self.job_id = None
