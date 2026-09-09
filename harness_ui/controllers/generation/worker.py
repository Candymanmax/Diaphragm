"""Worker event reduction and lifecycle supervision."""

import time

from modules.events import HarnessEvent
from modules.jobs import JobStoreError


class GenerationWorkerCommands:
    """Reduce isolated-worker events into application state and UI updates."""

    def recover_interrupted_jobs(self):
        for manifest in self.service.store.list_jobs():
            if manifest.get("status") not in {"running", "pausing", "cancelling"}:
                continue
            try:
                recovered = self.service.store.recover(manifest)
                self.diagnostics.append(
                    f"Recovered interrupted job {recovered['job_id']}", "warning"
                )
            except (JobStoreError, OSError) as error:
                self.diagnostics.append(str(error), "error")

    def handle_event(self, event):
        if not isinstance(event, HarnessEvent):
            return
        if event.kind == "log":
            self.diagnostics.append(
                event.message,
                str(event.payload.get("level", "info")),
                event.timestamp,
            )
        else:
            level = (
                "error"
                if "failed" in event.kind or "crashed" in event.kind
                else "warning"
                if "oom" in event.kind or "fallback" in event.kind or "paused" in event.kind
                else "info"
            )
            self.diagnostics.append(f"[{event.kind}] {event.message}", level, event.timestamp)
        runtime = event.payload.get("runtime")
        if isinstance(runtime, dict) and runtime:
            self._set("runtime_summary", self.runtime_summary(runtime))
        if event.kind == "worker.finished":
            self._set("worker_return_code", int(event.payload.get("return_code", 1)))
        elif event.kind == "worker.crashed":
            self._set("worker_return_code", 1)
            self._set("workspace_error_message", event.message)
        if event.kind.startswith(("job.", "script.", "chunk.")):
            self._set("manifest_updated_at", None)
        self._publish_snapshot()

    @staticmethod
    def runtime_summary(runtime):
        if not isinstance(runtime, dict) or not runtime:
            return "Runtime metrics appear after model load"
        parts = [
            str(runtime.get("device", "unknown")).upper(),
            f"section {runtime.get('current_section_words', '?')} words",
        ]
        if runtime.get("peak_vram_mb") is not None:
            parts.append(f"peak VRAM {runtime['peak_vram_mb']:.0f} MiB")
        if runtime.get("words_per_second") is not None:
            parts.append(f"{runtime['words_per_second']:.2f} words/s")
        if runtime.get("real_time_factor") is not None:
            parts.append(f"{runtime['real_time_factor']:.2f}x real-time")
        if runtime.get("oom_events"):
            parts.append(f"{runtime['oom_events']} OOM recoveries")
        return " · ".join(parts)

    def poll(self):
        for event in self.worker.poll():
            self.handle_event(event)
        if (
            self.worker.process is not None
            and not self.worker.running
            and not self._get("worker_finished_handled")
        ):
            for event in self.worker.poll():
                self.handle_event(event)
            self.finish_worker()
        now = time.monotonic()
        if now - float(self._get("last_job_refresh")) >= 1.0:
            job_id = self._get("current_job_id")
            self._refresh_jobs(select_job_id=job_id)
            self._refresh_current_job()

    def finish_worker(self):
        for event in self.worker.poll(limit=10000):
            self.handle_event(event)
        self._set("worker_finished_handled", True)
        process_exit = self.worker.exit_code()
        return_code = self._get("worker_return_code")
        return_code = process_exit if return_code is None else return_code
        job_id = self._get("current_job_id")
        if job_id:
            try:
                manifest = self.service.load_job(job_id)
                if manifest.get("status") in {"running", "pausing", "cancelling"}:
                    self.service.store.recover(manifest)
            except (JobStoreError, OSError):
                pass
        self.worker.close()
        self._set("pause_requested", False)
        self._set("cancel_requested", False)
        self._set("manifest_updated_at", None)
        self._refresh_jobs(select_job_id=job_id)
        self._refresh_current_job(force=True)
        if return_code == 0:
            self._status_message("Job completed", 5000)
            self.tabRequested.emit(2)
        elif return_code == 75:
            self._status_message("Job paused", 5000)
        elif return_code == 76:
            self._status_message("Job cancelled", 5000)
        else:
            self._status_message("Job stopped with an error; review the job and logs", 7000)
            self.logsRequested.emit()
        self._publish_snapshot()
