"""Safe discovery of published outputs recorded by job manifests."""

from __future__ import annotations

from pathlib import Path


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


__all__ = ("OutputCatalog",)
