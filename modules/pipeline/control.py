from __future__ import annotations

from modules.events import emit_event
from modules.jobs import JobControlRequested


PAUSED_EXIT_CODE = 75
CANCELLED_EXIT_CODE = 76


def check_control(
    store,
    manifest,
    script=None,
    event_callback=None,
):
    action = store.control_action(manifest["job_id"])

    if action is None:
        return

    status = "paused" if action == "pause" else "cancelled"
    manifest["status"] = status
    manifest["error"] = None

    if script is not None and script.get("status") == "running":
        script["status"] = status

    store.save(manifest)
    emit_event(
        event_callback,
        f"job.{status}",
        f"Job {status}",
        job_id=manifest["job_id"],
        script_id=script.get("id") if script is not None else None,
        payload={"status": status},
    )
    print(f"\nJob {status} after preserving completed chunks.")
    raise JobControlRequested(action)
