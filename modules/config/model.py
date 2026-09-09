from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

from .io import ensure_active_file, read_mapping
from .validation import validate_pipeline_config


@dataclass(frozen=True)
class PipelineConfig:
    voice: str = "male"
    model: str = "original"
    language: str = "en"
    chunk_size: int = 50
    min_chunk_size: int = 15
    output_format: str = "wav"
    retry_attempts: int = 3
    normalize_audio: bool = True
    merge_audio: bool = True
    retain_job_artifacts: bool = False
    sample_rate: int = 24000
    generation_max_words: int = 120
    splitting_mode: str = "automatic"
    automatic_min_words: int = 20
    automatic_max_words: int = 160
    vram_safety_margin_mb: int = 1024
    adaptive_growth_interval: int = 3
    cpu_fallback: bool = True
    device_preference: str = "auto"
    exaggeration: float = 0.6
    cfg_weight: float = 0.4
    temperature: float = 0.8
    repetition_penalty: float = 1.2
    min_p: float = 0.05
    top_p: float = 1.0
    top_k: int = 1000
    pause_min_ms: int = 100
    pause_max_ms: int = 250
    pause_mean_ms: float = 220.0
    pause_std_ms: float = 50.0
    loudness_target_lufs: float = -14.0

    def __post_init__(self):
        for name in ("voice",):
            value = getattr(self, name)
            if isinstance(value, str):
                object.__setattr__(self, name, value.strip())

        for name in ("model", "language", "splitting_mode", "device_preference"):
            value = getattr(self, name)
            if isinstance(value, str):
                object.__setattr__(self, name, value.strip().lower())

        if isinstance(self.output_format, str):
            object.__setattr__(
                self,
                "output_format",
                self.output_format.strip().lower().lstrip("."),
            )

        self.validate()

    @classmethod
    def from_file(cls, config_file, defaults_file=None):
        config_file = Path(config_file)

        if not config_file.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {config_file}"
            )

        values = {}

        if defaults_file is not None:
            defaults_file = Path(defaults_file)

            if not defaults_file.exists():
                raise FileNotFoundError(
                    f"Default configuration file not found: {defaults_file}"
                )

            values.update(read_mapping(defaults_file))

        values.update(read_mapping(config_file))
        defaults = cls()
        known_fields = {field.name for field in fields(cls)}
        unknown_fields = sorted(set(values) - known_fields)

        if unknown_fields:
            print(
                "Warning: ignoring unknown configuration keys: "
                + ", ".join(unknown_fields)
            )

        return cls(**{
            field.name: values.get(field.name, getattr(defaults, field.name))
            for field in fields(cls)
        })

    @staticmethod
    def ensure_active_file(config_file, defaults_file):
        return ensure_active_file(config_file, defaults_file)

    @staticmethod
    def _read_mapping(config_file):
        return read_mapping(config_file)

    def validate(self):
        validate_pipeline_config(self)
