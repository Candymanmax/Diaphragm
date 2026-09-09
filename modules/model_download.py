from __future__ import annotations

import argparse
import os
from pathlib import Path

from huggingface_hub import snapshot_download
from tqdm.auto import tqdm

from modules.app_settings import CredentialStore, CredentialStoreError
from modules.adapters.registry import (
    MODEL_DOWNLOAD_FILES,
    get_model_capabilities,
    model_is_installed,
)
from modules.model_inventory import record_model_inventory


MODEL_OPERATIONS = ("install", "update", "repair")


def _emit_progress(value):
    value = max(0, min(100, int(value)))
    print(f"MODEL_PROGRESS {value}", flush=True)


def _emit_message(value):
    print(f"MODEL_MESSAGE {str(value).strip()}", flush=True)


def _is_xet_download_error(error):
    message = str(error).lower()
    return "xet" in message or "hex hash" in message


def _snapshot_download_with_fallback(**kwargs):
    """Retry known hf-xet failures through Hugging Face's HTTP path."""

    try:
        return snapshot_download(**kwargs)
    except Exception as error:
        if not _is_xet_download_error(error):
            raise

        _emit_message(
            "The accelerated download failed; retrying with standard transfer..."
        )

        # huggingface_hub reads this value dynamically when selecting its
        # transfer backend. This mirrors the fallback in the pinned
        # Chatterbox loader and also works after a partial snapshot exists.
        import huggingface_hub.constants as hf_constants

        hf_constants.HF_HUB_DISABLE_XET = True
        return snapshot_download(**kwargs)


class _SnapshotProgress(tqdm):
    """Report the Hub's outer file progress in a process-friendly format."""

    def __init__(self, *args, **kwargs):
        self._tracks_snapshot = str(kwargs.get("desc", "")).startswith(
            "Fetching"
        )
        # Keep tqdm's counters active while suppressing its terminal renderer;
        # progress is sent to the GUI through the MODEL_PROGRESS protocol.
        kwargs["disable"] = False
        super().__init__(*args, **kwargs)
        self._report()

    def display(self, msg=None, pos=None):
        del msg, pos

    def update(self, amount=1):
        result = super().update(amount)
        self._report()
        return result

    def _report(self):
        if self._tracks_snapshot and self.total:
            # Keep the final ten percent for local integrity recording.
            _emit_progress(round((self.n / self.total) * 90))


def install_model(
    model_id,
    cache_root,
    *,
    operation="install",
    progress_callback=None,
):
    model_id = str(model_id).strip().lower()
    operation = str(operation).strip().lower()

    if operation not in MODEL_OPERATIONS:
        choices = ", ".join(MODEL_OPERATIONS)
        raise ValueError(f"Unknown model operation '{operation}'. Choose: {choices}")

    capability = get_model_capabilities(model_id)
    repository, required_files = MODEL_DOWNLOAD_FILES[model_id]
    hub_cache = Path(cache_root).expanduser().resolve()
    hub_cache.mkdir(parents=True, exist_ok=True)
    token = os.getenv("HF_TOKEN") or None

    if token is None:
        try:
            token = CredentialStore().token()
        except CredentialStoreError:
            token = None

    action = {
        "install": "Installing",
        "update": "Updating",
        "repair": "Repairing",
    }[operation]
    _emit_message(f"{action} {capability.display_name}...")
    _emit_progress(0)
    _snapshot_download_with_fallback(
        repo_id=repository,
        repo_type="model",
        revision="main",
        cache_dir=str(hub_cache),
        allow_patterns=list(required_files),
        token=token,
        force_download=operation == "repair",
        tqdm_class=_SnapshotProgress,
    )

    if not model_is_installed(model_id, hub_cache):
        raise RuntimeError(
            "The download completed without all files required by this model."
        )

    def record_progress(current, total):
        percentage = 90 + round((int(current) / max(1, int(total))) * 10)
        _emit_progress(percentage)

        if progress_callback is not None:
            progress_callback(current, total)

    _emit_message("Recording local model integrity...")
    record_model_inventory(
        model_id,
        hub_cache,
        progress_callback=record_progress,
    )
    _emit_progress(100)
    _emit_message(f"{capability.display_name} is ready to use.")
    return hub_cache


def main(argv=None):
    parser = argparse.ArgumentParser(description="Install a TTS model snapshot")
    parser.add_argument("model", choices=tuple(MODEL_DOWNLOAD_FILES))
    parser.add_argument("--cache-root", required=True)
    parser.add_argument("--operation", choices=MODEL_OPERATIONS, default="install")
    arguments = parser.parse_args(argv)
    install_model(
        arguments.model,
        arguments.cache_root,
        operation=arguments.operation,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
