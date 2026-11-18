"""Safe discovery of published outputs recorded by job manifests."""

from __future__ import annotations

from pathlib import Path

from modules.subtitles import subtitle_files

class OutputCatalog:
    """Resolve manifest output paths without escaping the output library."""

    def __init__(self, paths):
        self.paths = paths

    def paths_for(self, manifest):
        paths = []

        for script in manifest.get("scripts", []):
            relative = Path(str(script.get("published_output", "")))

            if relative.is_absolute():
                continue

            candidate = (self.paths.library_root / relative).resolve()
            final_root = self.paths.outputs_root.resolve()

            try:
                candidate.relative_to(final_root)
            except ValueError:
                continue

            if candidate.exists():
                paths.append(candidate)

        return paths

    def subtitles_for(self, audio):
        audio = Path(audio)
        if audio.suffix.lower() != ".wav" or not audio.is_file():
            return []
        root = self.paths.outputs_root.resolve()
        return [
            path for candidate in subtitle_files(audio)
            if (path := candidate.resolve()).is_relative_to(root) and path.is_file()
        ]


__all__ = ("OutputCatalog",)
