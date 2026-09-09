from __future__ import annotations

import json

from modules.events import emit_event
from modules.generator import VoiceGenerator
from modules.jobs import JobStoreError


class SharedGeneratorSession:
    """Lazily load and reuse one voice-conditioned model for a whole job."""

    def __init__(
        self,
        *,
        store,
        manifest,
        config,
        voice,
        app_paths,
        event_callback=None,
    ):
        self.store = store
        self.manifest = manifest
        self.config = config
        self.voice = voice
        self.app_paths = app_paths
        self.event_callback = event_callback
        self.generator = None

    def __call__(self, chunks_folder, audio_folder):
        if self.generator is None:
            config = self.config
            self.generator = VoiceGenerator(
                chunks_folder=chunks_folder,
                output_folder=audio_folder,
                voice_file=self.voice,
                language=config.language,
                model_name=config.model,
                sample_rate=config.sample_rate,
                retry_attempts=config.retry_attempts,
                output_format=config.output_format,
                generation_max_words=config.generation_max_words,
                splitting_mode=config.splitting_mode,
                automatic_min_words=config.automatic_min_words,
                automatic_max_words=config.automatic_max_words,
                vram_safety_margin_mb=config.vram_safety_margin_mb,
                adaptive_growth_interval=config.adaptive_growth_interval,
                cpu_fallback=config.cpu_fallback,
                device_preference=config.device_preference,
                runtime_profile_file=self.app_paths.runtime_profiles_file,
                model_cache_dir=self.app_paths.hub_cache_root,
                exaggeration=config.exaggeration,
                cfg_weight=config.cfg_weight,
                temperature=config.temperature,
                repetition_penalty=config.repetition_penalty,
                min_p=config.min_p,
                top_p=config.top_p,
                top_k=config.top_k,
                event_callback=self.event_callback,
            )
            self.manifest["runtime"] = self.generator.runtime_report()
            self.store.save(self.manifest)
            emit_event(
                self.event_callback,
                "runtime.updated",
                self.generator.runtime_summary(),
                job_id=self.manifest["job_id"],
                payload={
                    "runtime": self.manifest["runtime"],
                },
            )
        else:
            print(
                "Reusing the loaded model and cached voice conditioning "
                "for this script."
            )

        return self.generator

    def close(self):
        if self.generator is None:
            return

        try:
            self.generator.unload()
        except Exception as error:
            print(f"Warning: model unload failed: {error}")

        runtime = self.generator.runtime_report()
        self.manifest["runtime"] = runtime

        try:
            self.store.save(self.manifest)
        except (JobStoreError, OSError) as error:
            print(f"Warning: could not save runtime metrics: {error}")

        summary = self.generator.runtime_summary()
        print(f"RUNTIME_SUMMARY: {summary}")
        print(
            "RUNTIME_METRICS: "
            + json.dumps(runtime, separators=(",", ":"))
        )
        emit_event(
            self.event_callback,
            "runtime.final",
            summary,
            job_id=self.manifest["job_id"],
            payload={"runtime": runtime},
        )
