"""Repeatable UI/data-loading benchmarks using disposable synthetic fixtures."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
from importlib.metadata import version
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import wave


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 1
FIXTURE_VERSION = 1


def summarize(samples):
    ordered = sorted(samples)
    return {
        "median_ms": statistics.median(ordered),
        "p95_ms": ordered[math.ceil(len(ordered) * .95) - 1],
        "min_ms": ordered[0],
        "max_ms": ordered[-1],
        "samples_ms": samples,
    }


def git(*arguments):
    result = subprocess.run(
        ["git", *arguments], cwd=ROOT, capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def metadata(args):
    return {
        "schema": SCHEMA,
        "fixture_version": FIXTURE_VERSION,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "commit": git("rev-parse", "HEAD"),
        "tracked_changes": bool(git("diff", "HEAD", "--name-only")),
        "application_tree_sha256": application_fingerprint(),
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "environment": {
            "python": platform.python_version(),
            "os": platform.system(),
            "os_release": platform.release(),
            "architecture": platform.machine(),
            "logical_cpus": os.cpu_count(),
            "pyside6": version("PySide6"),
            "qt_platform": "offscreen",
            "qt_scale_factor": "1",
        },
        "settings": {"sizes": args.sizes, "samples": args.samples, "warmups": args.warmups},
    }


def application_fingerprint():
    """Identify tested source, including uncommitted edits, without storing paths."""
    digest = hashlib.sha256()
    files = [ROOT / "desktop_gui.py", ROOT / "requirements.txt"]
    for directory in ("harness_ui", "modules"):
        files.extend((ROOT / directory).rglob("*.py"))
    for path in sorted(files):
        digest.update(path.relative_to(ROOT).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def compare(before, after):
    for key in ("schema", "fixture_version", "harness_sha256", "environment", "settings"):
        if before[key] != after[key]:
            raise ValueError(f"Incompatible reports: {key} differs; capture matching runs.")
    if before["results"].keys() != after["results"].keys():
        raise ValueError("Incompatible reports: benchmark cases differ.")
    lines = ["case | before median ms | after median ms | change | after/before p95", "--- | ---: | ---: | ---: | ---:"]
    for name, old in before["results"].items():
        new = after["results"][name]
        base = old["wall"]["median_ms"]
        change = (new["wall"]["median_ms"] / base - 1) * 100
        ratio = new["wall"]["p95_ms"] / old["wall"]["p95_ms"]
        lines.append(f"{name} | {base:.3f} | {new['wall']['median_ms']:.3f} | {change:+.1f}% | {ratio:.2f}x")
    return "\n".join(lines)


def profile_calls(operation):
    """One separate, untimed pass: profiling overhead never enters timings."""
    counts = Counter()
    names = {"load", "load_records", "inspect_model_inventory", "_publish_snapshot"}

    def observe(frame, event, _arg):
        if event != "call":
            return
        name = frame.f_code.co_name
        if name not in names and name != "__init__":
            return
        owner = frame.f_locals.get("self")
        if name == "__init__" and type(owner).__name__ != "JobCardWidget":
            return
        path = Path(frame.f_code.co_filename)
        if not path.is_relative_to(ROOT):
            return
        key = f"{path.relative_to(ROOT).as_posix()}:{name}"
        counts[key] += 1

    previous = sys.getprofile()
    sys.setprofile(observe)
    try:
        operation()
    finally:
        sys.setprofile(previous)
    return dict(sorted(counts.items()))


def measure(operation, *, prepare, verify, drain, samples, warmups):
    walls, cpus = [], []
    for index in range(warmups + samples):
        prepare()
        drain()
        cpu_start = time.process_time_ns()
        wall_start = time.perf_counter_ns()
        value = operation()
        drain()
        wall = (time.perf_counter_ns() - wall_start) / 1e6
        cpu = (time.process_time_ns() - cpu_start) / 1e6
        verify(value)
        if index >= warmups:
            walls.append(wall)
            cpus.append(cpu)
    prepare()
    drain()
    counts = profile_calls(operation)
    drain()
    return {"wall": summarize(walls), "cpu": summarize(cpus), "calls": counts}


def populate_models(cache, mode):
    from modules.adapters.registry import MODEL_DOWNLOAD_FILES
    from modules.model_inventory.records import write_records

    records = {"models": {}}
    for model_id, (repo, files) in MODEL_DOWNLOAD_FILES.items():
        folder = cache / ("models--" + repo.replace("/", "--")) / "snapshots"
        # Several historical snapshots exercise discovery and best selection.
        for revision in range(3):
            snapshot = folder / f"revision-{revision:02d}"
            selected = files if mode == "recorded" and revision == 2 else files[:1]
            for filename in selected:
                target = snapshot / filename
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"synthetic model placeholder\n")
        records["models"][model_id] = {
            "repository": repo, "snapshot": "revision-02",
            "files": {name: {"size": 28} for name in files},
        }
    # Obtain actual placeholder sizes; no hashes or real weights are needed.
    for record in records["models"].values():
        folder = cache / ("models--" + record["repository"].replace("/", "--")) / "snapshots" / record["snapshot"]
        for name, entry in record["files"].items():
            if (folder / name).is_file():
                entry["size"] = (folder / name).stat().st_size
    write_records(cache, records)


def run(args):
    # Set before Qt imports. No personal QSettings, library, voices or models.
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["QT_SCALE_FACTOR"] = "1"
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"
    from PySide6.QtCore import QCoreApplication, QEvent, QTimer, Qt
    from PySide6.QtWidgets import QApplication, QDialog
    from harness_ui.main_window import HarnessMainWindow
    from harness_ui.model_manager.manager import ModelManagerWidget
    from modules.model_inventory import inspect_all_models

    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)

    def drain():
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()

    report = metadata(args)
    report["results"] = {}

    def record(name, operation, verify, prepare=lambda: None):
        result = measure(operation, prepare=prepare, verify=verify, drain=drain,
                         samples=args.samples, warmups=args.warmups)
        report["results"][name] = result
        print(f"{name}: median {result['wall']['median_ms']:.3f} ms; p95 {result['wall']['p95_ms']:.3f} ms", flush=True)

    def require(condition, message):
        if not condition:
            raise RuntimeError(f"Benchmark correctness check failed: {message}")

    with TemporaryDirectory(prefix="diaphragm-benchmark-") as temporary:
        root = Path(temporary).resolve()
        for size in args.sizes:
            fixture = root / f"jobs-{size}"
            fixture.mkdir()
            (fixture / "config.default.yaml").write_text("model: original\nlanguage: en\n", encoding="utf-8")
            window = HarnessMainWindow(fixture)
            try:
                window.resize(1200, 800)
                window.show()
                # Keep real controller calls but prevent unrelated timer callbacks.
                window.poll_timer.stop()
                window.autosave_timer.stop()
                drain()
                for timer in window.findChildren(QTimer):
                    timer.stop()
                store = window.service.store
                script = fixture / "benchmark-script.txt"
                script.write_text("A synthetic performance benchmark.\n" * 20, encoding="utf-8")
                voice = fixture / "benchmark-voice.wav"
                with wave.open(str(voice), "wb") as audio:
                    audio.setnchannels(1)
                    audio.setsampwidth(2)
                    audio.setframerate(24000)
                    audio.writeframes(b"\x00\x00" * 2400)
                for index in range(size):
                    manifest = store.create_job([script], {"model": "original", "language": "en"}, voice,
                                                name=f"Benchmark job {index:04d}", job_id=f"bench-{index:04d}")
                    manifest["scripts"][0]["chunks"] = [
                        {"id": f"chunk-{chunk:03d}", "status": "complete" if chunk < 10 else "pending"}
                        for chunk in range(20)
                    ]
                    manifest["archived"] = index % 5 == 0 and index != size - 1
                    manifest["created_at"] = (datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=index)).isoformat()
                    store.save(manifest)
                selected_id = f"bench-{size - 1:04d}"
                window.job_controller.refresh(select_job_id=selected_id)
                drain()
                expected_ids = [f"bench-{index:04d}" for index in reversed(range(size))]
                visible_ids = [f"bench-{index:04d}" for index in reversed(range(size))
                               if index % 5 != 0 or index == size - 1]

                def verify_list(value):
                    require([item["job_id"] for item in value] == expected_ids, "manifest count/order")

                def verify_ui(_value):
                    listing = window.workspace_view.jobs.job_list
                    ids = [listing.item(i).data(Qt.ItemDataRole.UserRole) for i in range(listing.count())]
                    require(ids == visible_ids, "visible job count/order/archive filtering")
                    require(listing.currentItem().data(Qt.ItemDataRole.UserRole) == selected_id, "selected job")
                    manifest = store.load(selected_id)
                    card = listing.itemWidget(listing.currentItem())
                    require(card.title_label.text() == manifest["name"], "updated card title")
                    complete, total = store.progress(manifest)
                    require(card.progress_bar.value() == complete and card.progress_bar.maximum() == total, "card progress")

                record(f"jobs/{size}/list_manifests", store.list_jobs, verify_list)
                record(f"jobs/{size}/refresh_unchanged", window.job_controller.refresh, verify_ui)
                change = [0]

                def change_title():
                    change[0] += 1
                    manifest = store.load(selected_id)
                    manifest["name"] = f"Changed job {change[0]}"
                    manifest["scripts"][0]["chunks"][10]["status"] = "complete" if change[0] % 2 else "pending"
                    store.save(manifest)

                record(f"jobs/{size}/refresh_changed", window.job_controller.refresh, verify_ui, change_title)
                record(f"jobs/{size}/idle_poll_due", window.generation_controller.poll, verify_ui,
                       lambda: window.ui_state.set("last_job_refresh", 0.0))
                record(f"jobs/{size}/idle_poll_not_due", window.generation_controller.poll, verify_ui,
                       lambda: window.ui_state.set("last_job_refresh", time.monotonic()))
                if size == args.sizes[0]:
                    cache = window.service.paths.hub_cache_root
                    controller = window.workspace_view.settings.settings_panel.model_controller
                    for mode in ("empty", "partial", "recorded"):
                        if mode != "empty":
                            populate_models(cache, mode)
                        inventory = inspect_all_models(cache)
                        expected = {key: (item.state, item.present_count, item.local_bytes) for key, item in inventory.items()}
                        require(all(item.state == {"empty": "missing", "partial": "partial", "recorded": "installed"}[mode] for item in inventory.values()), "model fixture state")

                        def verify_inventory(value):
                            require({key: (item.state, item.present_count, item.local_bytes) for key, item in value.items()} == expected, "inventory contents")

                        record(f"models/{mode}/scan_all", lambda: inspect_all_models(cache), verify_inventory)
                        record(f"models/{mode}/inspector_refresh", controller.refresh,
                               lambda _: require(controller.install_button.isEnabled() == (mode != "recorded"), "model action state"))
                    # Use the real Preferences controller's connected refresh path.
                    # Only its dialog shell is substituted to exclude unrelated
                    # credential and background checks from this focused case.
                    dialog = QDialog(window)
                    dialog.migration_active = False
                    manager = ModelManagerWidget(window.paths, fixture, parent=dialog)
                    dialog.model_manager = manager
                    window.ui_state.set("preferences_dialog", dialog)
                    try:
                        record("models/recorded/inspector_with_manager", controller.refresh,
                               lambda _: require(not manager.busy and all(card.inventory.state == "installed" for card in manager.cards.values()), "manager inventory"))
                    finally:
                        window.ui_state.set("preferences_dialog", None)
                        dialog.deleteLater()
            finally:
                window.close()
                window.deleteLater()
                drain()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--compare", type=Path, nargs=2, metavar=("BEFORE", "AFTER"))
    parser.add_argument("--sizes", type=int, nargs="+", default=[10, 100, 500])
    parser.add_argument("--samples", type=int, default=15)
    parser.add_argument("--warmups", type=int, default=3)
    args = parser.parse_args()
    if args.compare:
        try:
            print(compare(*(json.loads(path.read_text(encoding="utf-8")) for path in args.compare)))
        except (ValueError, KeyError) as error:
            parser.error(str(error))
        return
    if not args.output:
        parser.error("--output is required for a benchmark run")
    if args.output.exists():
        parser.error("output already exists; choose a new name to preserve earlier runs")
    if args.samples < 3 or args.warmups < 1 or any(size < 1 for size in args.sizes) or len(set(args.sizes)) != len(args.sizes):
        parser.error("use at least 3 samples, 1 warmup, and distinct positive sizes")
    report = run(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(report, output, indent=2)
        output.write("\n")


if __name__ == "__main__":
    main()
