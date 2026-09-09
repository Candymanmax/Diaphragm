from __future__ import annotations

from collections import deque
from pathlib import Path
import gc
import time

import torch
import torchaudio

from modules.adapters.base import GenerationOptions, SynthesisError
from modules.adapters.factory import create_tts_model_adapter
from modules.adapters.registry import get_model_capabilities
from modules.resources import (
    AdaptiveSectionPlanner,
    ResourceMonitor,
    RuntimeProfileStore,
    is_cuda_out_of_memory,
)

from .output import ChunkOutputWriter
from .runtime import (
    emit_runtime,
    print_after_load_resources,
    print_detected_resources,
    summarize_runtime,
)
from .text_sections import sentence_units, split_text, take_section


class VoiceGenerator:
    """Coordinate one loaded TTS model session and adaptive synthesis."""

    def __init__(
        self,
        chunks_folder,
        output_folder,
        voice_file,
        language="en",
        model_name="original",
        sample_rate=24000,
        retry_attempts=3,
        output_format="wav",
        generation_max_words=120,
        splitting_mode="automatic",
        automatic_min_words=20,
        automatic_max_words=160,
        vram_safety_margin_mb=1024,
        adaptive_growth_interval=3,
        cpu_fallback=True,
        device_preference="auto",
        runtime_profile_file="models/runtime_profiles.json",
        model_cache_dir=None,
        exaggeration=0.6,
        cfg_weight=0.4,
        temperature=0.8,
        repetition_penalty=1.2,
        min_p=0.05,
        top_p=1.0,
        top_k=1000,
        event_callback=None,
    ):
        self.chunks_folder = Path(chunks_folder)
        self.output_folder = Path(output_folder)
        self.voice_file = Path(voice_file)
        self.language = language.lower()
        self.model_name = model_name.lower()
        self.sample_rate = sample_rate
        self.retry_attempts = retry_attempts
        self.output_format = output_format.lower().lstrip(".")
        self.generation_max_words = generation_max_words
        self.splitting_mode = splitting_mode.lower()
        self.automatic_min_words = automatic_min_words
        self.automatic_max_words = automatic_max_words
        self.vram_safety_margin_mb = vram_safety_margin_mb
        self.adaptive_growth_interval = adaptive_growth_interval
        self.cpu_fallback = cpu_fallback
        self.device_preference = device_preference.lower()
        self.model_cache_dir = (
            Path(model_cache_dir).expanduser().resolve()
            if model_cache_dir is not None
            else None
        )
        self.exaggeration = exaggeration
        self.cfg_weight = cfg_weight
        self.temperature = temperature
        self.repetition_penalty = repetition_penalty
        self.min_p = min_p
        self.top_p = top_p
        self.top_k = top_k
        self.event_callback = event_callback
        self.adapter = None
        self.planner = None
        self._profile_saved = False
        self._load_fallback_used = False

        self.generation_options = GenerationOptions(
            language=self.language,
            exaggeration=self.exaggeration,
            cfg_weight=self.cfg_weight,
            temperature=self.temperature,
            repetition_penalty=self.repetition_penalty,
            min_p=self.min_p,
            top_p=self.top_p,
            top_k=self.top_k,
        )

        self.output_folder.mkdir(parents=True, exist_ok=True)
        self.device = self._select_device()
        self.monitor = ResourceMonitor(self.device)
        self.hardware_snapshot = self.monitor.snapshot()
        self.monitor.reset_peak()
        self.profile_store = RuntimeProfileStore(runtime_profile_file)

        self._print_detected_resources()

        try:
            self._load_adapter(self.device)
        except Exception as error:
            if (
                self.device == "cuda"
                and self.cpu_fallback
                and is_cuda_out_of_memory(error)
            ):
                print(
                    "CUDA ran out of memory while loading the model; "
                    "falling back to CPU."
                )
                self._release_adapter()
                self._release_cuda_memory()
                self.device = "cpu"
                self.monitor.set_active_device("cpu")
                self._load_fallback_used = True
                self._load_adapter("cpu")
            else:
                self._release_adapter()
                raise

        after_load = self.monitor.snapshot()
        self.planner = AdaptiveSectionPlanner(
            model_id=self.resolved_model_name,
            mode=self.splitting_mode,
            manual_words=self.generation_max_words,
            minimum_words=self.automatic_min_words,
            maximum_words=self.automatic_max_words,
            safety_margin_mb=self.vram_safety_margin_mb,
            growth_interval=self.adaptive_growth_interval,
            monitor=self.monitor,
            profile_store=self.profile_store,
            after_load_snapshot=after_load,
        )
        self.planner.cpu_fallback_used = self._load_fallback_used

        print(
            f"Loaded {self.adapter.display_name} on {self.device} "
            f"(language={self.language})"
        )
        self._print_after_load_resources(after_load)

    def _emit_runtime(self, kind, message):
        emit_runtime(self, kind, message)

    def _select_device(self):
        capabilities = get_model_capabilities(self.model_name)
        cuda_available = bool(torch.cuda.is_available())

        if self.device_preference == "cpu":
            return "cpu"

        if self.device_preference == "cuda":
            if cuda_available:
                return "cuda"

            if self.cpu_fallback:
                print("CUDA was requested but is unavailable; using CPU.")
                self._load_fallback_used = True
                return "cpu"

            raise RuntimeError(
                "CUDA was requested but is unavailable and CPU fallback "
                "is disabled"
            )

        if capabilities.recommended_device == "cpu":
            return "cpu"

        return "cuda" if cuda_available else "cpu"

    def _load_adapter(self, device):
        self.adapter = create_tts_model_adapter(
            model_name=self.model_name,
            language=self.language,
            device=device,
            cache_dir=self.model_cache_dir,
        )
        self.resolved_model_name = self.adapter.model_id
        print(f"Loading {self.adapter.display_name}...")

        try:
            self.adapter.load()
            self._prepare_voice_conditioning()
        except Exception:
            self._release_adapter()
            raise

    def _release_adapter(self):
        if self.adapter is None:
            return

        try:
            self.adapter.unload()
        finally:
            self.adapter = None

    @staticmethod
    def _release_cuda_memory():
        gc.collect()

        if torch.cuda.is_available():
            try:
                torch.cuda.empty_cache()
            except (AssertionError, RuntimeError):
                pass

    def _print_detected_resources(self):
        print_detected_resources(self)

    def _print_after_load_resources(self, snapshot):
        print_after_load_resources(self, snapshot)

    def _prepare_voice_conditioning(self):
        print(
            f"Preparing voice conditioning from "
            f"{self.voice_file.name}..."
        )
        self.adapter.prepare_voice(
            self.voice_file,
            exaggeration=self.exaggeration,
        )
        print("Voice conditioning cached for this job")

    @staticmethod
    def _sentence_units(text):
        return sentence_units(text)

    @staticmethod
    def _take_section(units, max_words):
        return take_section(units, max_words)

    def split_text(self, text, max_words=None):
        if max_words is None:
            max_words = (
                self.planner.current_words
                if self.planner is not None
                else self.generation_max_words
            )

        return split_text(text, max_words)

    def generate_part(self, text):
        for attempt in range(1, self.retry_attempts + 1):
            try:
                result = self.adapter.generate(
                    text,
                    self.generation_options,
                )
                wav = result.waveform

                if result.sample_rate != self.sample_rate:
                    wav = torchaudio.functional.resample(
                        wav,
                        result.sample_rate,
                        self.sample_rate,
                    )

                return wav
            except Exception as error:
                if is_cuda_out_of_memory(error):
                    raise

                if attempt >= self.retry_attempts:
                    raise SynthesisError(
                        f"Speech generation failed after "
                        f"{self.retry_attempts} attempts"
                    ) from error

                print(f"Generation attempt {attempt} failed: {error}")
                print(
                    f"Retrying ({attempt + 1}/{self.retry_attempts})"
                )
                self._release_cuda_memory()

        raise SynthesisError("Speech generation failed")

    def _fallback_to_cpu(self):
        if self.device != "cuda" or not self.cpu_fallback:
            return False

        print(
            "CUDA OOM persisted at the minimum safe section size; "
            "moving the loaded session to CPU."
        )
        self._release_adapter()
        self._release_cuda_memory()
        self.device = "cpu"
        self.monitor.set_active_device("cpu")
        self._load_adapter("cpu")
        snapshot = self.monitor.snapshot()
        self.planner.switch_to_cpu(snapshot)
        print(
            "RUNTIME_STATUS: CPU fallback | "
            f"section limit {self.planner.current_words} words"
        )
        self._emit_runtime(
            "runtime.cpu_fallback",
            f"CPU fallback | section limit "
            f"{self.planner.current_words} words",
        )
        return True

    def unload(self):
        if self.planner is not None and not self._profile_saved:
            try:
                self.planner.save_profile()
                self._profile_saved = True
            except (OSError, TypeError, ValueError) as error:
                print(f"Warning: could not save runtime profile: {error}")

        self._release_adapter()
        self._release_cuda_memory()

    def generate_chunk(self, text):
        units = deque(self._sentence_units(text))

        if not units:
            raise SynthesisError("Cannot generate speech from empty text")

        audio = []
        generated_sections = 0
        while units:
            limit = self.planner.current_words
            part = self._take_section(units, limit)

            if not part:
                break

            words = len(part.split())
            print(
                f"Generating section {generated_sections + 1} "
                f"({words} words, limit {limit}, {self.device})"
            )
            self.monitor.synchronize()
            started = time.perf_counter()

            try:
                wav = self.generate_part(part)
                self.monitor.synchronize()
            except Exception as error:
                if self.device != "cuda" or not is_cuda_out_of_memory(error):
                    raise

                previous_limit = self.planner.current_words
                reduced_limit = self.planner.record_oom(words)
                self._release_cuda_memory()

                for sentence in reversed(self._sentence_units(part)):
                    units.appendleft(sentence)

                print(
                    f"CUDA OOM at {words} words; section limit reduced "
                    f"from {previous_limit} to {reduced_limit}."
                )
                print(
                    "RUNTIME_STATUS: CUDA OOM recovery | "
                    f"section limit {reduced_limit} words"
                )
                self._emit_runtime(
                    "runtime.oom_recovery",
                    f"CUDA OOM recovery | section limit "
                    f"{reduced_limit} words",
                )

                if words <= self.planner.minimum_words:
                    if self._fallback_to_cpu():
                        continue

                    raise SynthesisError(
                        "CUDA ran out of memory at the configured minimum "
                        "section size and CPU fallback is disabled"
                    ) from error

                continue

            elapsed = time.perf_counter() - started
            audio_seconds = wav.shape[-1] / self.sample_rate
            self._release_cuda_memory()
            previous_limit = self.planner.current_words
            chosen_limit = self.planner.record_success(
                words,
                elapsed,
                audio_seconds,
            )

            if chosen_limit > previous_limit:
                print(
                    f"VRAM headroom is stable; section limit increased "
                    f"from {previous_limit} to {chosen_limit}."
                )
                print(
                    "RUNTIME_STATUS: CUDA stable | "
                    f"section limit {chosen_limit} words"
                )
                self._emit_runtime(
                    "runtime.grew",
                    f"CUDA stable | section limit {chosen_limit} words",
                )

            audio.append(wav)
            generated_sections += 1
            del wav

        if not audio:
            raise SynthesisError("Speech generation produced no audio")

        return torch.cat(audio, dim=1)

    def runtime_report(self):
        if self.planner is None:
            return {}

        return self.planner.report()

    def runtime_summary(self):
        return summarize_runtime(self.runtime_report())

    def run(
        self,
        chunk_files=None,
        output_folder=None,
        before_chunk=None,
        after_chunk=None,
        on_chunk_error=None,
    ):
        return ChunkOutputWriter(self).run(
            chunk_files=chunk_files,
            output_folder=output_folder,
            before_chunk=before_chunk,
            after_chunk=after_chunk,
            on_chunk_error=on_chunk_error,
        )
