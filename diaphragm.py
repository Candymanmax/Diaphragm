"""Run Diaphragm text-to-speech jobs from a terminal."""

import argparse
from dataclasses import replace
import multiprocessing
from pathlib import Path
import signal
import sys


PROGRESS_EVENTS = {
    "script.started",
    "script.completed",
    "script.failed",
    "chunk.started",
    "chunk.failed",
    "job.completed",
    "job.failed",
    "job.interrupted",
    "worker.crashed",
}


def _show_progress(events):
    for event in events:
        if event.kind in PROGRESS_EVENTS or (
            event.kind == "log" and event.payload.get("level") == "error"
        ):
            print(event.message, file=sys.stderr, flush=True)


def _run_worker(service, job_id, *, mode):
    from modules.worker import JobWorkerProcess

    worker = JobWorkerProcess(service.paths)
    pause_requested = False
    pause_sent = False
    started = False

    def request_pause(_signum, _frame):
        nonlocal pause_requested
        pause_requested = True

    previous_handler = signal.signal(signal.SIGINT, request_pause)
    try:
        worker.start(job_id, mode=mode, terminal=True)
        while worker.running:
            events = worker.poll()
            _show_progress(events)
            # Resume preparation clears old control files before job.started.
            started = started or any(event.kind == "job.started" for event in events)
            if started and pause_requested and not pause_sent:
                service.request_pause(job_id)
                pause_sent = True
                print("Pausing at the next safe checkpoint…", file=sys.stderr, flush=True)
            worker.process.join(timeout=0.1)
        while events := worker.poll():
            _show_progress(events)
        return worker.exit_code()
    finally:
        try:
            worker.terminate()
            worker.close()
        finally:
            signal.signal(signal.SIGINT, previous_handler)


def _run_job(service, job_id, *, mode, command):
    from modules.jobs import JobStoreError

    exit_code = _run_worker(service, job_id, mode=mode)
    manifest = service.load_job(job_id)
    if exit_code != 0:
        if manifest["status"] == "paused":
            print(
                f"Job {job_id} paused. Resume with `{command} jobs resume {job_id}`.",
                file=sys.stderr,
            )
        else:
            print(f"Job {job_id} stopped ({manifest['status']}).", file=sys.stderr)
        return exit_code if exit_code is not None and exit_code > 0 else 1

    outputs = service.output_paths(manifest)
    if manifest["status"] != "complete" or len(outputs) != len(manifest["scripts"]):
        raise JobStoreError(f"Published output is missing for job {job_id}")
    for output in outputs:
        print(output)
    return 0


def _list_jobs(service):
    jobs = [job for job in service.list_jobs() if not job.get("temporary")]
    if not jobs:
        print("No saved jobs yet.")
        return
    print("JOB ID\tSTATUS\tSCRIPTS")
    for job in jobs:
        scripts = ", ".join(script["name"] for script in job["scripts"])
        print(f"{job['job_id']}\t{job['status']}\t{scripts}")


def _show_job(service, job):
    print(f"Job {job['job_id']} ({job['status']})")
    complete, total = service.store.progress(job)
    if total:
        print(f"{complete}/{total} chunks complete")
    for script in job["scripts"]:
        print(f"{script['name']} ({script['status']})")
    if job.get("error"):
        print(job["error"])
    if job["status"] == "complete":
        for output in service.output_paths(job):
            print(output)


def _ensure_packaged_runtime(data_root):
    if not getattr(sys, "frozen", False):
        return

    from modules.jobs import JobStoreError
    from modules.runtime_manager import RuntimeManager

    manager = RuntimeManager(data_root)
    runtime = manager.ready_python()
    if runtime is None:
        raise JobStoreError("Open Diaphragm.exe once to set up the speech runtime, then retry.")
    manager.activate(runtime)


def _run_command(args, command):
    from yaml import YAMLError

    from modules.app_settings import SettingsRepository
    from modules.contracts import JobRequest
    from modules.jobs import JobStoreError
    from modules.service import TTSHarnessService

    try:
        bundle_root = Path(__file__).resolve().parent
        install_root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else bundle_root
        defaults_file = install_root / "config.default.yaml"
        if not defaults_file.is_file():
            defaults_file = bundle_root / "config.default.yaml"
        paths = SettingsRepository.for_application(install_root, defaults_file=defaults_file).paths
        if args.legacy_library:
            paths = replace(paths, library_root=paths.data_root / "cli")
            command += " --legacy-library"
        service = TTSHarnessService(paths)
        if args.command == "generate":
            _ensure_packaged_runtime(paths.data_root)
            manifest = service.create_job(JobRequest(
                scripts=tuple(str(script) for script in args.scripts),
                voice_override=str(args.voice),
                origin="cli",
            ))
            job_id = manifest["job_id"]
            print(f"Created job {job_id}", file=sys.stderr, flush=True)
            return _run_job(service, job_id, mode="prepared", command=command)

        if args.job_command == "list":
            _list_jobs(service)
            return 0

        manifest = service.load_job(args.job_id)
        if args.job_command == "show":
            _show_job(service, manifest)
            return 0

        if manifest.get("temporary"):
            raise JobStoreError("Save and run this draft from the desktop before resuming it.")
        _ensure_packaged_runtime(paths.data_root)
        job_id = manifest["job_id"]
        print(f"Resuming job {job_id}", file=sys.stderr, flush=True)
        return _run_job(service, job_id, mode="resume", command=command)
    except (JobStoreError, OSError, RuntimeError, ValueError, YAMLError) as error:
        print(f"diaphragm: {error}", file=sys.stderr)
        return 1


def main(argv=None):
    command = Path(sys.executable).name if getattr(sys, "frozen", False) else "python -m diaphragm"
    parser = argparse.ArgumentParser(prog=command, description=__doc__)
    parser.add_argument("--legacy-library", action="store_true", help="Use the original CLI job library")
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate", help="Generate audio from text files")
    generate.add_argument("scripts", nargs="+", type=Path, metavar="SCRIPT.txt")
    generate.add_argument("--voice", required=True, type=Path, metavar="VOICE.wav")
    jobs = commands.add_parser("jobs", help="Inspect and resume saved jobs")
    job_commands = jobs.add_subparsers(dest="job_command", required=True)
    job_commands.add_parser("list", help="List saved jobs")
    show = job_commands.add_parser("show", help="Show job status and progress")
    show.add_argument("job_id", metavar="JOB_ID")
    resume = job_commands.add_parser("resume", help="Continue a saved job")
    resume.add_argument("job_id", metavar="JOB_ID")
    args = parser.parse_args(argv)

    if args.command == "generate":
        args.scripts = tuple(script.expanduser().resolve() for script in args.scripts)
        args.voice = args.voice.expanduser().resolve()
        inputs = [(script, ".txt") for script in args.scripts]
        inputs.append((args.voice, ".wav"))
        for path, suffix in inputs:
            if path.suffix.lower() != suffix or not path.is_file():
                generate.error(f"Expected an existing {suffix} file: {path}")

    try:
        return _run_command(args, command)
    except ImportError as error:
        print(f"diaphragm: {error}", file=sys.stderr)
        print("Run the project launcher once, then use its Python runtime.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
