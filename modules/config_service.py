"""Active pipeline-configuration loading and atomic persistence."""

from __future__ import annotations

from dataclasses import asdict
import os
from pathlib import Path
import uuid

import yaml

from modules.config import PipelineConfig


class PipelineConfigService:
    """Resolve and persist config files against explicit application paths."""

    def __init__(self, paths):
        self.paths = paths
        self.project_root = paths.library_root
        self.install_root = paths.install_root

    def project_path(self, value):
        path = Path(value).expanduser()

        if not path.is_absolute():
            path = self.project_root / path

        return path.resolve()

    def config_paths(
        self,
        config_file="config.yaml",
        defaults_file="config.default.yaml",
    ):
        config_value = Path(config_file).expanduser()
        defaults_value = Path(defaults_file).expanduser()
        return (
            self.paths.config_file
            if config_value == Path("config.yaml")
            else self.project_path(config_value),
            self.paths.defaults_file
            if defaults_value == Path("config.default.yaml")
            else (
                defaults_value.resolve()
                if defaults_value.is_absolute()
                else (self.install_root / defaults_value).resolve()
            ),
        )

    def load(
        self,
        config_file="config.yaml",
        defaults_file="config.default.yaml",
    ):
        config_path, defaults_path = self.config_paths(
            config_file,
            defaults_file,
        )
        PipelineConfig.ensure_active_file(config_path, defaults_path)
        return PipelineConfig.from_file(
            config_path,
            defaults_file=defaults_path,
        )

    def save(
        self,
        values,
        config_file="config.yaml",
        defaults_file="config.default.yaml",
    ):
        config_path, _ = self.config_paths(config_file, defaults_file)
        config = (
            values
            if isinstance(values, PipelineConfig)
            else PipelineConfig(**dict(values))
        )
        config_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = config_path.parent / (
            f".{config_path.name}.{uuid.uuid4().hex}.tmp"
        )

        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as file:
                yaml.safe_dump(
                    asdict(config),
                    file,
                    sort_keys=False,
                    allow_unicode=True,
                )
                file.flush()
                os.fsync(file.fileno())

            os.replace(temporary, config_path)
        finally:
            if temporary.exists():
                temporary.unlink()

        return config


__all__ = ("PipelineConfigService",)
