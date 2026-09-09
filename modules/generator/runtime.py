from __future__ import annotations

from modules.events import emit_event


def emit_runtime(generator, kind, message):
    try:
        runtime = generator.runtime_report()
    except (AttributeError, RuntimeError):
        runtime = {}

    emit_event(
        getattr(generator, "event_callback", None),
        kind,
        message,
        payload={"runtime": runtime},
    )


def print_detected_resources(generator):
    snapshot = generator.hardware_snapshot
    system_text = (
        f"{snapshot.available_system_ram_mb:.0f}/"
        f"{snapshot.total_system_ram_mb:.0f} MiB RAM available"
        if (
            snapshot.available_system_ram_mb is not None
            and snapshot.total_system_ram_mb is not None
        )
        else "system RAM unavailable"
    )

    if snapshot.cuda_available and snapshot.gpu_name:
        vram_text = (
            f", {snapshot.free_vram_mb:.0f}/"
            f"{snapshot.total_vram_mb:.0f} MiB VRAM free"
            if (
                snapshot.free_vram_mb is not None
                and snapshot.total_vram_mb is not None
            )
            else ""
        )
        print(
            f"Detected GPU: {snapshot.gpu_name}{vram_text}; "
            f"{system_text}"
        )
        emit_event(
            getattr(generator, "event_callback", None),
            "resources.detected",
            f"Detected {snapshot.gpu_name}",
            payload={"resources": snapshot.to_dict()},
        )
    else:
        print(f"CUDA unavailable; {system_text}")
        emit_event(
            getattr(generator, "event_callback", None),
            "resources.detected",
            "CUDA unavailable; using system memory",
            payload={"resources": snapshot.to_dict()},
        )


def print_after_load_resources(generator, snapshot):
    if generator.device == "cuda" and snapshot.free_vram_mb is not None:
        memory = (
            f"{snapshot.free_vram_mb:.0f} MiB VRAM free after model "
            f"and voice loading (safety margin "
            f"{generator.vram_safety_margin_mb} MiB)"
        )
    elif snapshot.available_system_ram_mb is not None:
        memory = (
            f"{snapshot.available_system_ram_mb:.0f} MiB system RAM "
            "available after model and voice loading"
        )
    else:
        memory = "memory remaining after model load is unavailable"

    print(f"Memory after load: {memory}")
    print(
        "RUNTIME_STATUS: "
        f"{generator.device.upper()} | {generator.splitting_mode.title()} | "
        f"section limit {generator.planner.current_words} words"
    )
    generator._emit_runtime(
        "runtime.ready",
        f"{generator.device.upper()} | section limit "
        f"{generator.planner.current_words} words",
    )


def summarize_runtime(report):
    if not report:
        return "Runtime metrics unavailable"

    peak = report.get("peak_vram_mb")
    speed = report.get("words_per_second")
    rtf = report.get("real_time_factor")
    details = [
        str(report.get("device", "unknown")).upper(),
        f"section {report.get('current_section_words')} words",
    ]

    if peak is not None:
        details.append(f"peak VRAM {peak:.0f} MiB")

    if speed is not None:
        details.append(f"{speed:.2f} words/s")

    if rtf is not None:
        details.append(f"{rtf:.2f}x real-time")

    return " | ".join(details)
