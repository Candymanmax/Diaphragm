from __future__ import annotations

import argparse

from modules.adapters.registry import MODEL_ADAPTER_NAMES

from .removal import remove_model_inventory
from .verification import verify_model_inventory


def emit_progress(current, total):
    percentage = int(round((int(current) / max(1, int(total))) * 100))
    print(f"MODEL_PROGRESS {max(0, min(100, percentage))}", flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Inspect and maintain locally cached TTS models"
    )
    parser.add_argument("operation", choices=("verify", "remove"))
    parser.add_argument("model", choices=MODEL_ADAPTER_NAMES)
    parser.add_argument("--cache-root", required=True)
    arguments = parser.parse_args(argv)

    if arguments.operation == "verify":
        report = verify_model_inventory(
            arguments.model,
            arguments.cache_root,
            progress_callback=emit_progress,
        )
        print(f"MODEL_MESSAGE {report.message}", flush=True)
        return 0 if report.valid else 1

    removed_bytes = remove_model_inventory(
        arguments.model,
        arguments.cache_root,
        progress_callback=emit_progress,
    )
    print(
        f"MODEL_MESSAGE Removed local model files ({removed_bytes} bytes).",
        flush=True,
    )
    return 0
