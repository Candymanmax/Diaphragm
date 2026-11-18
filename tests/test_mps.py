"""Regression coverage for Metal selection, recovery, and memory reporting."""

from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import torch

from modules.config import PipelineConfig
from modules.generator import VoiceGenerator
from modules.resources import (
    AdaptiveSectionPlanner, ResourceMonitor, ResourceSnapshot, RuntimeProfileStore,
    is_accelerator_out_of_memory, is_mps_unsupported_error, release_device_memory,
)


def mps_snapshot():
    return ResourceSnapshot(
        active_device="mps", cuda_available=False, gpu_name="Apple Metal (MPS)",
        total_vram_mb=None, free_vram_mb=None, allocated_vram_mb=None,
        reserved_vram_mb=None, peak_vram_mb=None, total_system_ram_mb=16000,
        available_system_ram_mb=6000, mps_available=True,
        mps_allocated_memory_mb=1000, mps_driver_memory_mb=2048,
        mps_recommended_memory_mb=8192,
    )


class MPSTests(unittest.TestCase):
    def make_generator(self, folder, words=8, fallback=True):
        generator = VoiceGenerator.__new__(VoiceGenerator)
        generator.model_name = "original"
        generator.device_preference = "mps"
        generator.device = "mps"
        generator.cpu_fallback = fallback
        generator._load_fallback_used = False
        generator.sample_rate = 24000
        generator.generation_max_words = words
        generator.adapter = None
        generator.monitor = SimpleNamespace(
            synchronize=lambda: None, snapshot=mps_snapshot,
            set_active_device=lambda device: None,
        )
        generator.planner = AdaptiveSectionPlanner(
            model_id="original", mode="manual", manual_words=words,
            minimum_words=2, maximum_words=160, safety_margin_mb=1024,
            growth_interval=1, monitor=generator.monitor,
            profile_store=RuntimeProfileStore(Path(folder)/"profiles.json"),
            after_load_snapshot=mps_snapshot(),
        )
        return generator

    def test_config_accepts_and_serializes_mps(self):
        config = PipelineConfig(device_preference=" MPS ")
        self.assertEqual(config.device_preference, "mps")
        self.assertEqual(PipelineConfig(**asdict(config)).device_preference, "mps")

    def test_device_selection_respects_recommendations_and_explicit_overrides(self):
        cases = (
            ("original", "auto", True, True, "mps"),
            ("original", "auto", False, True, "cpu"),
            ("original", "mps", True, False, "mps"),
            ("original", "mps", False, True, "cpu"),
            ("original", "mps", False, False, None),
            ("original", "cpu", True, False, "cpu"),
            ("nano", "auto", True, True, "cpu"),
            ("nano", "mps", True, False, "mps"),
        )
        with TemporaryDirectory() as folder:
            for model, preference, available, fallback, expected in cases:
                with self.subTest(model=model, preference=preference, available=available):
                    generator = self.make_generator(folder, fallback=fallback)
                    generator.model_name = model
                    generator.device_preference = preference
                    with patch("torch.cuda.is_available", return_value=False), patch(
                        "torch.backends.mps.is_available", return_value=available
                    ):
                        if expected is None:
                            with self.assertRaisesRegex(RuntimeError, "CPU fallback"):
                                generator._select_device()
                        else:
                            self.assertEqual(generator._select_device(), expected)

    def test_mps_oom_requeues_text_at_a_smaller_limit(self):
        with TemporaryDirectory() as folder:
            generator = self.make_generator(folder)
            calls = []

            def generate(text):
                calls.append(text)
                if len(calls) == 1:
                    raise RuntimeError("MPS backend out of memory")
                return torch.zeros(1, 8)

            with patch.object(generator, "generate_part", side_effect=generate), patch.object(
                generator, "_release_accelerator_memory"
            ):
                audio = generator.generate_chunk("One two three four. Five six seven eight.")
            self.assertEqual([len(text.split()) for text in calls], [8, 4, 4])
            self.assertEqual(generator.planner.oom_events, 1)
            self.assertEqual(tuple(audio.shape), (1, 16))

    def test_unsupported_mps_operation_retries_only_failed_section_on_cpu(self):
        with TemporaryDirectory() as folder:
            generator = self.make_generator(folder, words=2)
            calls = []

            def generate(text):
                calls.append((generator.device, text))
                if len(calls) == 2:
                    raise RuntimeError("adapter failed") from NotImplementedError(
                        "operator not implemented for MPS"
                    )
                return torch.ones(1, 4)

            with patch.object(generator, "generate_part", side_effect=generate), patch.object(
                generator, "_load_adapter"
            ), patch.object(generator, "_release_accelerator_memory"):
                audio = generator.generate_chunk("One two. Three four.")
            self.assertEqual(calls, [
                ("mps", "One two."), ("mps", "Three four."), ("cpu", "Three four."),
            ])
            self.assertTrue(generator.planner.cpu_fallback_used)
            self.assertEqual(generator.runtime_report()["device"], "cpu")
            self.assertEqual(tuple(audio.shape), (1, 8))

    def test_mps_errors_respect_disabled_cpu_fallback(self):
        errors = (
            NotImplementedError("operator not implemented for MPS"),
            RuntimeError("MPS backend out of memory"),
        )
        with TemporaryDirectory() as folder:
            for error in errors:
                with self.subTest(error=error):
                    generator = self.make_generator(folder, words=2, fallback=False)
                    with patch.object(generator, "generate_part", side_effect=error), patch.object(
                        generator, "_release_accelerator_memory"
                    ):
                        with self.assertRaises((NotImplementedError, RuntimeError)):
                            generator.generate_chunk("One two.")
                    self.assertEqual(generator.device, "mps")

    def test_mps_load_failure_reloads_on_cpu_and_reports_the_fallback(self):
        calls = []

        def load(generator, device):
            calls.append(device)
            if device == "mps":
                raise RuntimeError("loader failed") from RuntimeError(
                    "MPS backend out of memory"
                )
            generator.adapter = SimpleNamespace(display_name="Test model")
            generator.resolved_model_name = "original"

        with TemporaryDirectory() as folder, patch.object(
            VoiceGenerator, "_select_device", return_value="mps"
        ), patch.object(VoiceGenerator, "_load_adapter", autospec=True, side_effect=load), patch.object(
            VoiceGenerator, "_print_detected_resources"
        ), patch.object(VoiceGenerator, "_print_after_load_resources"), patch.object(
            VoiceGenerator, "_release_accelerator_memory"
        ):
            generator = VoiceGenerator(
                folder, folder, "voice.wav", cpu_fallback=True,
                runtime_profile_file=Path(folder)/"profiles.json",
            )
        self.assertEqual(calls, ["mps", "cpu"])
        self.assertEqual(generator.device, "cpu")
        self.assertEqual(generator.runtime_report()["device"], "cpu")
        self.assertTrue(generator.runtime_report()["cpu_fallback_used"])

    def test_unsupported_mps_error_skips_retries_before_session_fallback(self):
        with TemporaryDirectory() as folder:
            generator = self.make_generator(folder)
            generator.retry_attempts = 3
            generator.generation_options = None
            generator.adapter = SimpleNamespace(generate=lambda *args: None)
            with patch.object(generator.adapter, "generate", side_effect=NotImplementedError(
                "operator is not implemented for MPS"
            )) as generate:
                with self.assertRaises(NotImplementedError):
                    generator.generate_part("One two.")
            generate.assert_called_once()

    def test_mps_monitor_reports_shared_memory_and_cleans_its_cache(self):
        mib = 1024 * 1024
        with patch("torch.cuda.is_available", return_value=False), patch(
            "torch.backends.mps.is_available", return_value=True
        ), patch("torch.mps.current_allocated_memory", return_value=1000*mib), patch(
            "torch.mps.driver_allocated_memory", return_value=2000*mib
        ), patch("torch.mps.recommended_max_memory", return_value=8000*mib), patch(
            "torch.mps.synchronize"
        ) as synchronize, patch("torch.mps.empty_cache") as empty_cache:
            monitor = ResourceMonitor("mps")
            monitor.synchronize()
            current = monitor.snapshot()
            release_device_memory("mps")
        self.assertTrue(current.mps_available)
        self.assertEqual(current.mps_allocated_memory_mb, 1000)
        self.assertEqual(current.mps_driver_memory_mb, 2000)
        self.assertIsNone(current.total_vram_mb)
        self.assertIsNone(current.peak_vram_mb)
        synchronize.assert_called_once()
        empty_cache.assert_called_once()

    def test_mps_headroom_profiles_and_growth_are_separate_from_cpu(self):
        current = mps_snapshot()
        self.assertEqual(current.accelerator_headroom_mb, 6000)
        with TemporaryDirectory() as folder:
            generator = self.make_generator(folder)
            planner = generator.planner
            planner.mode = "automatic"
            planner.current_words = planner._initial_words(current)
            self.assertEqual(planner.current_words, 120)
            planner.record_success(120, 1, 2)
            self.assertGreater(planner.current_words, 120)
            planner.save_profile()
            saved = planner.profile_store.get(planner.profile_id)
            self.assertEqual(saved["device_name"], "Apple Metal (MPS)")
            self.assertEqual(saved["total_memory_mb"], 8192)
            self.assertNotEqual(planner.profile_id, planner.profile_store.profile_id(
                "original", "CPU", current.total_system_ram_mb
            ))

    def test_wrapped_mps_errors_preserve_ordinary_failures(self):
        error = RuntimeError("adapter failed")
        error.__cause__ = RuntimeError("MPS backend out of memory")
        self.assertTrue(is_accelerator_out_of_memory(error, "mps"))
        self.assertFalse(is_accelerator_out_of_memory(error, "cpu"))
        error.__cause__ = NotImplementedError("operator not implemented for MPS")
        self.assertTrue(is_mps_unsupported_error(error))
        self.assertFalse(is_mps_unsupported_error(RuntimeError("missing model file")))
