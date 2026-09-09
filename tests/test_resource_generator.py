import unittest
from unittest.mock import patch

import torch

from modules.generator import VoiceGenerator


class FakeMonitor:
    def synchronize(self):
        pass


class ReducingPlanner:
    def __init__(self, current_words=8, minimum_words=2):
        self.current_words = current_words
        self.minimum_words = minimum_words
        self.successful_words = []
        self.oom_words = []

    def record_oom(self, words):
        self.oom_words.append(words)
        self.current_words = max(
            self.minimum_words,
            self.current_words // 2,
        )
        return self.current_words

    def record_success(self, words, elapsed, audio_seconds):
        self.successful_words.append(words)
        return self.current_words


class ResourceAwareGeneratorTests(unittest.TestCase):
    @staticmethod
    def _generator(planner=None):
        generator = VoiceGenerator.__new__(VoiceGenerator)
        generator.generation_max_words = 120
        generator.planner = planner
        generator.device = "cuda"
        generator.cpu_fallback = False
        generator.sample_rate = 24000
        generator.monitor = FakeMonitor()
        return generator

    @staticmethod
    def _device_generator(
        model_name="original",
        device_preference="auto",
        cpu_fallback=True,
    ):
        generator = VoiceGenerator.__new__(VoiceGenerator)
        generator.model_name = model_name
        generator.device_preference = device_preference
        generator.cpu_fallback = cpu_fallback
        generator._load_fallback_used = False
        return generator

    def test_auto_device_uses_cuda_for_the_original_model(self):
        generator = self._device_generator()

        with patch(
            "modules.generator.engine.torch.cuda.is_available",
            return_value=True,
        ):
            self.assertEqual(generator._select_device(), "cuda")

    def test_auto_device_honors_nano_cpu_recommendation(self):
        generator = self._device_generator(model_name="nano")

        with patch(
            "modules.generator.engine.torch.cuda.is_available",
            return_value=True,
        ):
            self.assertEqual(generator._select_device(), "cpu")

    def test_explicit_unavailable_cuda_requires_fallback(self):
        generator = self._device_generator(
            device_preference="cuda",
            cpu_fallback=False,
        )

        with patch(
            "modules.generator.engine.torch.cuda.is_available",
            return_value=False,
        ):
            with self.assertRaisesRegex(RuntimeError, "CPU fallback"):
                generator._select_device()

    def test_split_text_prefers_complete_sentence_boundaries(self):
        generator = self._generator()
        text = (
            "This first sentence has exactly six words. "
            "This second sentence also has six words. "
            "The last one is short."
        )

        parts = generator.split_text(text, max_words=10)

        self.assertEqual(len(parts), 3)
        self.assertTrue(parts[0].endswith("words."))
        self.assertTrue(parts[1].endswith("words."))
        self.assertTrue(parts[2].endswith("short."))

    def test_oversized_single_sentence_has_a_safe_word_fallback(self):
        generator = self._generator()
        text = "one two three four five six seven eight nine ten."

        parts = generator.split_text(text, max_words=4)

        self.assertEqual([len(part.split()) for part in parts], [4, 4, 2])

    def test_cuda_oom_requeues_text_at_a_smaller_sentence_limit(self):
        planner = ReducingPlanner(current_words=8, minimum_words=2)
        generator = self._generator(planner)
        calls = []

        def generate_part(text):
            calls.append(len(text.split()))

            if len(calls) == 1:
                raise RuntimeError("CUDA out of memory on GPU")

            return torch.zeros(1, 16)

        with (
            patch.object(generator, "generate_part", side_effect=generate_part),
            patch.object(generator, "_release_cuda_memory"),
        ):
            audio = generator.generate_chunk(
                "One two three four. Five six seven eight."
            )

        self.assertEqual(calls, [8, 4, 4])
        self.assertEqual(planner.oom_words, [8])
        self.assertEqual(planner.successful_words, [4, 4])
        self.assertEqual(tuple(audio.shape), (1, 32))

    def test_cuda_oom_at_minimum_uses_cpu_fallback(self):
        planner = ReducingPlanner(current_words=2, minimum_words=2)
        generator = self._generator(planner)
        generator.cpu_fallback = True
        calls = []

        def generate_part(text):
            calls.append(generator.device)

            if len(calls) == 1:
                raise RuntimeError("CUDA out of memory on GPU")

            return torch.zeros(1, 8)

        def fallback():
            generator.device = "cpu"
            return True

        with (
            patch.object(generator, "generate_part", side_effect=generate_part),
            patch.object(generator, "_fallback_to_cpu", side_effect=fallback),
            patch.object(generator, "_release_cuda_memory"),
        ):
            audio = generator.generate_chunk("One two.")

        self.assertEqual(calls, ["cuda", "cpu"])
        self.assertEqual(tuple(audio.shape), (1, 8))


if __name__ == "__main__":
    unittest.main()
