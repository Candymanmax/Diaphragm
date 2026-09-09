from __future__ import annotations

import math

from modules.adapters.registry import (
    MODEL_ADAPTER_NAMES,
    validate_model_configuration,
)


GENERATION_CONTROL_LIMITS = {
    "exaggeration": (0.0, 1.0),
    "cfg_weight": (0.0, 1.0),
    "temperature": (0.1, 1.5),
    "repetition_penalty": (1.0, 2.0),
    "min_p": (0.0, 0.2),
    "top_p": (0.1, 1.0),
    "top_k": (1, 1000),
}


def validate_pipeline_config(config):
    if not isinstance(config.voice, str) or not config.voice.strip():
        raise ValueError("Config 'voice' must be a non-empty string")

    if not isinstance(config.model, str) or not config.model.strip():
        raise ValueError("Config 'model' must be a non-empty string")

    if config.model not in MODEL_ADAPTER_NAMES:
        choices = ", ".join(MODEL_ADAPTER_NAMES)
        raise ValueError(f"Config 'model' must be one of: {choices}")

    if not isinstance(config.language, str) or not config.language.strip():
        raise ValueError("Config 'language' must be a non-empty string")

    validate_model_configuration(config.model, config.language)

    integer_fields = {
        "chunk_size": config.chunk_size,
        "min_chunk_size": config.min_chunk_size,
        "retry_attempts": config.retry_attempts,
        "sample_rate": config.sample_rate,
        "generation_max_words": config.generation_max_words,
        "automatic_min_words": config.automatic_min_words,
        "automatic_max_words": config.automatic_max_words,
        "adaptive_growth_interval": config.adaptive_growth_interval,
        "top_k": config.top_k,
        "pause_min_ms": config.pause_min_ms,
        "pause_max_ms": config.pause_max_ms,
    }

    for name, value in integer_fields.items():
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"Config '{name}' must be an integer")

        if value <= 0:
            raise ValueError(f"Config '{name}' must be greater than zero")

    top_k_minimum, top_k_maximum = GENERATION_CONTROL_LIMITS["top_k"]

    if not top_k_minimum <= config.top_k <= top_k_maximum:
        raise ValueError(
            "Config 'top_k' must be between "
            f"{top_k_minimum} and {top_k_maximum} "
            "to avoid unstable dialogue generation"
        )

    if (
        isinstance(config.vram_safety_margin_mb, bool)
        or not isinstance(config.vram_safety_margin_mb, int)
    ):
        raise ValueError(
            "Config 'vram_safety_margin_mb' must be an integer"
        )

    if config.vram_safety_margin_mb < 0:
        raise ValueError("Config 'vram_safety_margin_mb' cannot be negative")

    if config.min_chunk_size > config.chunk_size:
        raise ValueError(
            "Config 'min_chunk_size' cannot exceed 'chunk_size'"
        )

    if config.pause_min_ms > config.pause_max_ms:
        raise ValueError(
            "Config 'pause_min_ms' cannot exceed 'pause_max_ms'"
        )

    if config.automatic_min_words > config.automatic_max_words:
        raise ValueError(
            "Config 'automatic_min_words' cannot exceed "
            "'automatic_max_words'"
        )

    if config.splitting_mode not in {"automatic", "manual"}:
        raise ValueError(
            "Config 'splitting_mode' must be automatic or manual"
        )

    if config.device_preference not in {"auto", "cuda", "cpu"}:
        raise ValueError(
            "Config 'device_preference' must be auto, cuda, or cpu"
        )

    float_fields = {
        "exaggeration": config.exaggeration,
        "cfg_weight": config.cfg_weight,
        "temperature": config.temperature,
        "repetition_penalty": config.repetition_penalty,
        "min_p": config.min_p,
        "top_p": config.top_p,
        "pause_mean_ms": config.pause_mean_ms,
        "pause_std_ms": config.pause_std_ms,
        "loudness_target_lufs": config.loudness_target_lufs,
    }

    for name, value in float_fields.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Config '{name}' must be a number")

        if not math.isfinite(value):
            raise ValueError(f"Config '{name}' must be finite")

    for name in (
        "exaggeration",
        "cfg_weight",
        "temperature",
        "repetition_penalty",
        "min_p",
        "top_p",
    ):
        minimum, maximum = GENERATION_CONTROL_LIMITS[name]
        value = getattr(config, name)

        if not minimum <= value <= maximum:
            raise ValueError(
                f"Config '{name}' must be between "
                f"{minimum:g} and {maximum:g} "
                "to avoid unstable dialogue generation"
            )

    if not config.pause_min_ms <= config.pause_mean_ms <= config.pause_max_ms:
        raise ValueError(
            "Config 'pause_mean_ms' must be between the pause limits"
        )

    if config.pause_std_ms < 0:
        raise ValueError("Config 'pause_std_ms' cannot be negative")

    if not -60 <= config.loudness_target_lufs <= 0:
        raise ValueError(
            "Config 'loudness_target_lufs' must be between -60 and zero"
        )

    if not isinstance(config.output_format, str):
        raise ValueError("Config 'output_format' must be a string")

    if config.output_format.lower().lstrip(".") != "wav":
        raise ValueError("Only WAV output is currently supported")

    for name, value in {
        "normalize_audio": config.normalize_audio,
        "merge_audio": config.merge_audio,
        "retain_job_artifacts": config.retain_job_artifacts,
        "cpu_fallback": config.cpu_fallback,
    }.items():
        if not isinstance(value, bool):
            raise ValueError(f"Config '{name}' must be true or false")
