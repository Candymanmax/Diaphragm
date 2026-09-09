"""Voice-reference resolution and private-library import operations."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import uuid

from modules.jobs import JobStoreError


class VoiceLibrary:
    """Manage WAV references inside the selected personal library."""

    def __init__(self, paths):
        self.paths = paths
        self.project_root = paths.library_root

    def resolve(self, value, config_folder=None):
        configured = Path(str(value)).expanduser()
        config_folder = Path(config_folder or self.project_root)
        candidates = [configured, config_folder / configured]

        if configured.parent == Path("."):
            candidates.extend((
                self.paths.voices_root / configured,
                config_folder / "voices" / configured,
            ))

        if not configured.suffix:
            candidates.extend(
                candidate.with_suffix(".wav")
                for candidate in tuple(candidates)
            )

        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()

        for directory in {candidate.parent for candidate in candidates}:
            if not directory.is_dir():
                continue

            for candidate in directory.iterdir():
                if (
                    candidate.is_file()
                    and candidate.suffix.lower() == ".wav"
                    and candidate.stem.lower() == configured.stem.lower()
                ):
                    return candidate.resolve()

        raise FileNotFoundError(
            f"Voice reference not found: {value}. Select a WAV file or "
            "place one in the voices folder."
        )

    def list(self):
        folder = self.paths.voices_root
        folder.mkdir(parents=True, exist_ok=True)
        return sorted(
            (
                path
                for path in folder.iterdir()
                if path.is_file() and path.suffix.lower() == ".wav"
            ),
            key=lambda path: path.name.lower(),
        )

    def import_file(self, source):
        source = Path(source).expanduser().resolve()

        if not source.is_file() or source.suffix.lower() != ".wav":
            raise JobStoreError("Voice references must be WAV files")

        folder = self.paths.voices_root
        folder.mkdir(parents=True, exist_ok=True)
        destination = folder / source.name
        index = 2

        while destination.exists() and destination.resolve() != source:
            destination = folder / f"{source.stem}-{index}{source.suffix.lower()}"
            index += 1

        if destination.resolve() != source:
            temporary = folder / f".{destination.name}.{uuid.uuid4().hex}.tmp"

            try:
                shutil.copy2(source, temporary)
                os.replace(temporary, destination)
            finally:
                if temporary.exists():
                    temporary.unlink()

        return destination.resolve()


__all__ = ("VoiceLibrary",)
