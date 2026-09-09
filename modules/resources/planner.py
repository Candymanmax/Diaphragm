from __future__ import annotations

import math

from .profiles import utc_now


class AdaptiveSectionPlanner:
    """Select and tune inference section sizes from memory headroom."""

    def __init__(
        self,
        model_id,
        mode,
        manual_words,
        minimum_words,
        maximum_words,
        safety_margin_mb,
        growth_interval,
        monitor,
        profile_store,
        after_load_snapshot,
    ):
        self.model_id = str(model_id).lower()
        self.mode = str(mode).lower()
        self.manual_words = int(manual_words)
        self.minimum_words = int(minimum_words)
        self.maximum_words = int(maximum_words)

        if self.mode == "manual":
            self.minimum_words = min(
                self.minimum_words,
                self.manual_words,
            )
            self.maximum_words = max(
                self.maximum_words,
                self.manual_words,
            )
        self.safety_margin_mb = int(safety_margin_mb)
        self.growth_interval = int(growth_interval)
        self.monitor = monitor
        self.profile_store = profile_store
        self.after_load_snapshot = after_load_snapshot
        self.fallback_snapshot = None
        self.device = after_load_snapshot.active_device
        self.success_streak = 0
        self.oom_events = 0
        self.growth_events = 0
        self.total_words = 0
        self.synthesis_seconds = 0.0
        self.audio_seconds = 0.0
        self.sections_generated = 0
        self.largest_successful_words = 0
        self.smallest_oom_words = None
        self.cpu_fallback_used = False

        memory_mb = (
            after_load_snapshot.total_vram_mb
            if self.device == "cuda"
            else after_load_snapshot.total_system_ram_mb
        )
        device_name = (
            after_load_snapshot.gpu_name
            if self.device == "cuda"
            else "CPU"
        )
        self.profile_id = profile_store.profile_id(
            self.model_id,
            device_name,
            memory_mb,
        )
        self.profile = profile_store.get(self.profile_id)
        self.current_words = self._initial_words(after_load_snapshot)
        self.initial_words = self.current_words

    def _clamp(self, words):
        return max(
            self.minimum_words,
            min(self.maximum_words, int(words)),
        )

    def _initial_words(self, snapshot):
        if self.mode == "manual":
            return self.manual_words

        profiled = self.profile.get("recommended_words")

        if isinstance(profiled, int) and profiled > 0:
            initial = profiled
        elif self.device == "cuda":
            usable = max(
                0.0,
                float(snapshot.free_vram_mb or 0)
                - self.safety_margin_mb,
            )

            if usable < 512:
                initial = self.minimum_words
            elif usable < 1024:
                initial = 30
            elif usable < 2048:
                initial = 50
            elif usable < 4096:
                initial = 80
            elif usable < 6144:
                initial = 120
            else:
                initial = self.maximum_words
        else:
            available = float(snapshot.available_system_ram_mb or 0)

            if available and available < 2048:
                initial = self.minimum_words
            elif available and available < 4096:
                initial = 40
            elif available and available < 8192:
                initial = 80
            else:
                initial = min(120, self.maximum_words)

        smallest_oom = self.profile.get("smallest_oom_words")

        if isinstance(smallest_oom, int) and smallest_oom > self.minimum_words:
            initial = min(initial, smallest_oom - 1)

        return self._clamp(initial)

    def record_oom(self, attempted_words):
        attempted_words = max(1, int(attempted_words))
        self.oom_events += 1
        self.success_streak = 0

        if self.smallest_oom_words is None:
            self.smallest_oom_words = attempted_words
        else:
            self.smallest_oom_words = min(
                self.smallest_oom_words,
                attempted_words,
            )

        reduced = max(
            self.minimum_words,
            min(
                self.current_words - 1,
                math.floor(self.current_words * 0.7),
                attempted_words - 1,
            ),
        )
        self.current_words = self._clamp(reduced)
        return self.current_words

    def record_success(self, words, elapsed_seconds, audio_seconds):
        words = max(0, int(words))
        self.total_words += words
        self.synthesis_seconds += max(0.0, float(elapsed_seconds))
        self.audio_seconds += max(0.0, float(audio_seconds))
        self.sections_generated += 1
        self.largest_successful_words = max(
            self.largest_successful_words,
            words,
        )

        if self.mode != "automatic" or self.device != "cuda":
            return self.current_words

        representative_words = max(
            self.minimum_words,
            math.floor(self.current_words * 0.75),
        )

        if words < representative_words:
            self.success_streak = 0
            return self.current_words

        self.success_streak += 1

        if self.success_streak < self.growth_interval:
            return self.current_words

        snapshot = self.monitor.snapshot()
        free_vram = float(snapshot.free_vram_mb or 0)
        required_free = self.safety_margin_mb + 512

        if free_vram <= required_free or self.current_words >= self.maximum_words:
            return self.current_words

        candidate = max(
            self.current_words + 10,
            math.ceil(self.current_words * 1.15),
        )
        smallest_oom = self.smallest_oom_words

        if smallest_oom is None:
            profiled_oom = self.profile.get("smallest_oom_words")
            smallest_oom = (
                profiled_oom
                if isinstance(profiled_oom, int)
                else None
            )

        if smallest_oom is not None:
            candidate = min(candidate, smallest_oom - 1)

        candidate = self._clamp(candidate)

        if candidate > self.current_words:
            self.current_words = candidate
            self.growth_events += 1
            self.success_streak = 0

        return self.current_words

    def switch_to_cpu(self, snapshot):
        self.device = "cpu"
        self.monitor.set_active_device("cpu")
        self.success_streak = 0
        self.cpu_fallback_used = True
        self.fallback_snapshot = snapshot

        if self.mode == "automatic":
            self.current_words = self._clamp(
                min(self.current_words, self.manual_words)
            )

    def report(self, final_snapshot=None):
        final_snapshot = final_snapshot or self.monitor.snapshot()
        words_per_second = (
            self.total_words / self.synthesis_seconds
            if self.synthesis_seconds > 0
            else None
        )
        real_time_factor = (
            self.synthesis_seconds / self.audio_seconds
            if self.audio_seconds > 0
            else None
        )

        return {
            "device": self.device,
            "cuda_available": final_snapshot.cuda_available,
            "gpu_name": final_snapshot.gpu_name,
            "total_vram_mb": final_snapshot.total_vram_mb,
            "free_vram_after_load_mb": (
                self.after_load_snapshot.free_vram_mb
            ),
            "available_system_ram_after_load_mb": (
                (
                    self.fallback_snapshot
                    or self.after_load_snapshot
                ).available_system_ram_mb
            ),
            "peak_vram_mb": final_snapshot.peak_vram_mb,
            "splitting_mode": self.mode,
            "initial_section_words": self.initial_words,
            "current_section_words": self.current_words,
            "minimum_section_words": self.minimum_words,
            "maximum_section_words": self.maximum_words,
            "vram_safety_margin_mb": self.safety_margin_mb,
            "sections_generated": self.sections_generated,
            "words_generated": self.total_words,
            "synthesis_seconds": round(self.synthesis_seconds, 3),
            "audio_seconds": round(self.audio_seconds, 3),
            "words_per_second": (
                round(words_per_second, 3)
                if words_per_second is not None
                else None
            ),
            "real_time_factor": (
                round(real_time_factor, 3)
                if real_time_factor is not None
                else None
            ),
            "oom_events": self.oom_events,
            "growth_events": self.growth_events,
            "cpu_fallback_used": self.cpu_fallback_used,
        }

    def save_profile(self):
        prior_runs = int(self.profile.get("runs", 0))
        prior_ooms = int(self.profile.get("oom_events", 0))
        prior_largest = int(
            self.profile.get("largest_successful_words", 0)
        )
        prior_smallest_oom = self.profile.get("smallest_oom_words")
        smallest_oom = self.smallest_oom_words

        if isinstance(prior_smallest_oom, int):
            smallest_oom = (
                prior_smallest_oom
                if smallest_oom is None
                else min(prior_smallest_oom, smallest_oom)
            )

        report = self.report()
        profiled_cuda_device = (
            self.after_load_snapshot.active_device == "cuda"
        )
        profile = {
            "model_id": self.model_id,
            "device_name": (
                self.after_load_snapshot.gpu_name
                if profiled_cuda_device
                else "CPU"
            ),
            "total_memory_mb": (
                self.after_load_snapshot.total_vram_mb
                if profiled_cuda_device
                else self.after_load_snapshot.total_system_ram_mb
            ),
            "recommended_words": self.current_words,
            "largest_successful_words": max(
                prior_largest,
                self.largest_successful_words,
            ),
            "smallest_oom_words": smallest_oom,
            "runs": prior_runs + 1,
            "oom_events": prior_ooms + self.oom_events,
            "last_peak_vram_mb": report["peak_vram_mb"],
            "last_words_per_second": report["words_per_second"],
            "last_real_time_factor": report["real_time_factor"],
            "updated_at": utc_now(),
        }
        self.profile_store.save_profile(self.profile_id, profile)
        self.profile = profile
