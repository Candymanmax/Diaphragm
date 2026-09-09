"""Mapping between settings controls and the validated pipeline config."""

from __future__ import annotations

from dataclasses import dataclass

from modules.adapters.registry import get_model_capabilities
from modules.config import PipelineConfig


@dataclass(frozen=True)
class SettingsConfigurationSnapshot:
    """Immutable summary of the current generation configuration."""

    model: str
    voice: str
    language: str
    splitting_mode: str
    sample_rate: int


class SettingsConfigMapper:
    """Read, write, validate, and persist inspector control values."""

    def __init__(self, *, panel, service, behavior):
        self.panel = panel
        self.service = service
        self.behavior = behavior

    def snapshot(self):
        config = self.to_config()
        return SettingsConfigurationSnapshot(
            model=config.model,
            voice=config.voice,
            language=config.language,
            splitting_mode=config.splitting_mode,
            sample_rate=config.sample_rate,
        )

    def set_config(self, config):
        panel = self.panel

        if not isinstance(config, PipelineConfig):
            config = PipelineConfig(**dict(config))

        panel.loading = True

        try:
            panel.refresh_voices(config.voice)
            index = panel.model.findData(config.model)
            panel.model.setCurrentIndex(max(0, index))
            self.behavior.model_changed()
            language_index = panel.language.findData(config.language)
            panel.language.setCurrentIndex(max(0, language_index))
            panel.voice.setCurrentText(config.voice)
            panel.preset.setCurrentText("Custom")
            panel.chunk_size.setValue(config.chunk_size)
            panel.min_chunk_size.setValue(config.min_chunk_size)
            panel.output_format.setCurrentIndex(
                max(0, panel.output_format.findData(config.output_format))
            )
            panel.retry_attempts.setValue(config.retry_attempts)
            panel.normalize_audio.setChecked(config.normalize_audio)
            panel.merge_audio.setChecked(config.merge_audio)
            panel.retain_job_artifacts.setChecked(
                config.retain_job_artifacts
            )
            panel.sample_rate.setValue(config.sample_rate)
            panel.generation_max_words.setValue(
                config.generation_max_words
            )
            panel.splitting_mode.setCurrentText(config.splitting_mode)
            panel.automatic_min_words.setValue(config.automatic_min_words)
            panel.automatic_max_words.setValue(config.automatic_max_words)
            panel.vram_safety_margin_mb.setValue(
                config.vram_safety_margin_mb
            )
            panel.adaptive_growth_interval.setValue(
                config.adaptive_growth_interval
            )
            panel.cpu_fallback.setChecked(config.cpu_fallback)
            panel.device_preference.setCurrentText(
                config.device_preference
            )
            panel.exaggeration.setValue(config.exaggeration)
            panel.cfg_weight.setValue(config.cfg_weight)
            panel.temperature.setValue(config.temperature)
            panel.repetition_penalty.setValue(config.repetition_penalty)
            panel.min_p.setValue(config.min_p)
            panel.top_p.setValue(config.top_p)
            panel.top_k.setValue(config.top_k)
            panel.pause_min_ms.setValue(config.pause_min_ms)
            panel.pause_max_ms.setValue(config.pause_max_ms)
            panel.pause_mean_ms.setValue(config.pause_mean_ms)
            panel.pause_std_ms.setValue(config.pause_std_ms)
            panel.loudness_target_lufs.setValue(
                config.loudness_target_lufs
            )
            self.behavior.apply_splitting_mode()
        finally:
            panel.loading = False

        panel.validation.hide()

    def to_config(self):
        panel = self.panel
        language = panel.language.currentData() or "en"
        output_format = panel.output_format.currentData() or "wav"
        return PipelineConfig(
            voice=panel.voice.currentText().strip(),
            model=panel.model_controller.model_id(),
            language=str(language),
            chunk_size=panel.chunk_size.value(),
            min_chunk_size=panel.min_chunk_size.value(),
            output_format=str(output_format),
            retry_attempts=panel.retry_attempts.value(),
            normalize_audio=panel.normalize_audio.isChecked(),
            merge_audio=panel.merge_audio.isChecked(),
            retain_job_artifacts=panel.retain_job_artifacts.isChecked(),
            sample_rate=panel.sample_rate.value(),
            generation_max_words=panel.generation_max_words.value(),
            splitting_mode=panel.splitting_mode.currentText(),
            automatic_min_words=panel.automatic_min_words.value(),
            automatic_max_words=panel.automatic_max_words.value(),
            vram_safety_margin_mb=panel.vram_safety_margin_mb.value(),
            adaptive_growth_interval=(
                panel.adaptive_growth_interval.value()
            ),
            cpu_fallback=panel.cpu_fallback.isChecked(),
            device_preference=panel.device_preference.currentText(),
            exaggeration=panel.exaggeration.value(),
            cfg_weight=panel.cfg_weight.value(),
            temperature=panel.temperature.value(),
            repetition_penalty=panel.repetition_penalty.value(),
            min_p=panel.min_p.value(),
            top_p=panel.top_p.value(),
            top_k=panel.top_k.value(),
            pause_min_ms=panel.pause_min_ms.value(),
            pause_max_ms=panel.pause_max_ms.value(),
            pause_mean_ms=panel.pause_mean_ms.value(),
            pause_std_ms=panel.pause_std_ms.value(),
            loudness_target_lufs=panel.loudness_target_lufs.value(),
        )

    def save(self):
        panel = self.panel

        try:
            config = self.to_config()
            config = self.service.save_config(config)
        except Exception as error:
            panel.validation.setText(str(error))
            panel.validation.show()
            return None

        panel.validation.hide()
        panel.configSaved.emit(config)
        return config

    def reset_defaults(self):
        panel = self.panel

        try:
            defaults = PipelineConfig.from_file(
                self.service.paths.defaults_file
            )
        except Exception as error:
            panel.validation.setText(str(error))
            panel.validation.show()
            return

        self.set_config(defaults)
        panel.notify_change()

    def summary(self):
        config = self.to_config()
        mode = (
            f"automatic {config.automatic_min_words}–"
            f"{config.automatic_max_words} words"
            if config.splitting_mode == "automatic"
            else f"manual {config.generation_max_words} words"
        )
        return (
            f"{get_model_capabilities(config.model).display_name} · "
            f"{config.language.upper()} · {config.device_preference.upper()} · "
            f"{mode} · {config.sample_rate} Hz"
        )


__all__ = ("SettingsConfigMapper", "SettingsConfigurationSnapshot")
