from pathlib import Path
from tempfile import TemporaryDirectory
import inspect
import unittest
from unittest.mock import patch

import torch

from modules.adapters.base import (
    AdapterNotLoadedError,
    GenerationOptions,
    ModelCompatibilityError,
    SynthesisError,
)
from modules.adapters.chatterbox import (
    ChatterboxNanoAdapter,
    ChatterboxOriginalAdapter,
    ChatterboxTurboAdapter,
    ChatterboxV3Adapter,
)
from modules.adapters.factory import (
    create_tts_model_adapter,
    resolve_model_adapter_name,
)
from modules.adapters.registry import MODEL_DOWNLOAD_FILES


class FakeModel:
    sr = 22050

    def __init__(self):
        self.prepare_calls = []
        self.generate_calls = []

    def prepare_conditionals(self, voice_file, **kwargs):
        self.prepare_calls.append((voice_file, kwargs))

    def generate(self, **kwargs):
        self.generate_calls.append(kwargs)
        return torch.tensor([0.0, 0.25, -0.25], dtype=torch.float64)


class FakeModelClass:
    load_calls = []
    instance = None

    @classmethod
    def reset(cls):
        cls.load_calls = []
        cls.instance = None

    @classmethod
    def from_pretrained(cls, device, **kwargs):
        cls.load_calls.append({"device": device, **kwargs})
        cls.instance = FakeModel()
        return cls.instance


class LocalFakeModelClass(FakeModelClass):
    local_load_calls = []

    @classmethod
    def reset(cls):
        super().reset()
        cls.local_load_calls = []

    @classmethod
    def from_local(cls, ckpt_dir, device, **kwargs):
        cls.local_load_calls.append(
            {"ckpt_dir": Path(ckpt_dir), "device": device, **kwargs}
        )
        cls.instance = FakeModel()
        return cls.instance


class FailingGenerationModel(FakeModel):
    def generate(self, **kwargs):
        raise ValueError("mock generation failure")


class FailingGenerationModelClass(FakeModelClass):
    @classmethod
    def from_pretrained(cls, device, **kwargs):
        cls.instance = FailingGenerationModel()
        return cls.instance


class LegacyMultilingualModelClass:
    @classmethod
    def from_pretrained(cls, device):
        return FakeModel()


class ModelAdapterTests(unittest.TestCase):
    def setUp(self):
        self.options = GenerationOptions(
            language="es",
            exaggeration=0.7,
            cfg_weight=0.3,
            temperature=0.75,
            repetition_penalty=1.1,
            min_p=0.08,
            top_p=0.9,
            top_k=750,
        )

    def test_every_adapter_loads_prepares_generates_and_unloads(self):
        cases = (
            (ChatterboxOriginalAdapter, {}, False, False),
            (ChatterboxTurboAdapter, {}, False, True),
            (ChatterboxV3Adapter, {"t3_model": "v3"}, True, False),
            (ChatterboxNanoAdapter, {"nano": True}, False, True),
        )

        with TemporaryDirectory() as temp_folder:
            voice_file = Path(temp_folder) / "voice.wav"
            voice_file.touch()

            for adapter_class, load_options, uses_language, turbo in cases:
                with self.subTest(adapter=adapter_class.model_id):
                    FakeModelClass.reset()

                    with patch.object(
                        adapter_class,
                        "model_class",
                        FakeModelClass,
                    ):
                        adapter = adapter_class(device="cpu")
                        returned_adapter = adapter.load()

                        self.assertIs(returned_adapter, adapter)
                        self.assertEqual(
                            FakeModelClass.load_calls,
                            [{"device": "cpu", **load_options}],
                        )

                        adapter.prepare_voice(
                            voice_file,
                            exaggeration=self.options.exaggeration,
                        )
                        adapter.prepare_voice(
                            voice_file,
                            exaggeration=self.options.exaggeration,
                        )

                        self.assertEqual(
                            len(FakeModelClass.instance.prepare_calls),
                            1,
                        )
                        prepared_kwargs = (
                            FakeModelClass.instance.prepare_calls[0][1]
                        )
                        self.assertEqual(
                            prepared_kwargs["exaggeration"],
                            0.0 if turbo else self.options.exaggeration,
                        )

                        result = adapter.generate(
                            "Adapter test sentence.",
                            self.options,
                        )

                        self.assertEqual(result.sample_rate, 22050)
                        self.assertEqual(tuple(result.waveform.shape), (1, 3))
                        self.assertEqual(result.waveform.dtype, torch.float32)
                        self.assertEqual(result.waveform.device.type, "cpu")

                        generation_kwargs = (
                            FakeModelClass.instance.generate_calls[0]
                        )
                        self.assertEqual(
                            "language_id" in generation_kwargs,
                            uses_language,
                        )

                        if uses_language:
                            self.assertEqual(
                                generation_kwargs["language_id"],
                                "es",
                            )

                        if turbo:
                            self.assertEqual(
                                generation_kwargs["top_k"],
                                self.options.top_k,
                            )
                            self.assertNotIn(
                                "exaggeration",
                                generation_kwargs,
                            )
                            self.assertNotIn("cfg_weight", generation_kwargs)
                            self.assertNotIn("min_p", generation_kwargs)
                        else:
                            self.assertEqual(
                                generation_kwargs["exaggeration"],
                                self.options.exaggeration,
                            )
                            self.assertEqual(
                                generation_kwargs["cfg_weight"],
                                self.options.cfg_weight,
                            )
                            self.assertEqual(
                                generation_kwargs["min_p"],
                                self.options.min_p,
                            )

                        adapter.unload()
                        self.assertFalse(adapter.loaded)

                        with self.assertRaises(AdapterNotLoadedError):
                            _ = adapter.sample_rate

    def test_variant_adapters_report_clear_legacy_package_errors(self):
        cases = (
            (ChatterboxV3Adapter, "t3_model='v3'"),
            (ChatterboxNanoAdapter, "nano=True"),
        )

        for adapter_class, expected_option in cases:
            with self.subTest(adapter=adapter_class.model_id):
                with patch.object(
                    adapter_class,
                    "model_class",
                    LegacyMultilingualModelClass,
                ):
                    adapter = adapter_class(device="cpu")

                    with self.assertRaisesRegex(
                        ModelCompatibilityError,
                        expected_option,
                    ):
                        adapter.load()

    def test_installed_snapshot_loads_without_a_second_huggingface_download(self):
        with TemporaryDirectory() as temp_folder:
            hub = Path(temp_folder) / "models" / "huggingface" / "hub"
            snapshot = (
                hub
                / "models--ResembleAI--chatterbox"
                / "snapshots"
                / "revision"
            )
            snapshot.mkdir(parents=True)
            for filename in MODEL_DOWNLOAD_FILES["original"][1]:
                (snapshot / filename).write_bytes(b"cached")

            LocalFakeModelClass.reset()

            with (
                patch.object(
                    ChatterboxOriginalAdapter,
                    "model_class",
                    LocalFakeModelClass,
                ),
                patch.object(
                    LocalFakeModelClass,
                    "from_pretrained",
                    side_effect=AssertionError(
                        "an installed model must not download again"
                    ),
                ),
            ):
                adapter = ChatterboxOriginalAdapter(
                    device="cpu",
                    cache_dir=hub,
                )
                adapter.load()

            self.assertEqual(len(LocalFakeModelClass.local_load_calls), 1)
            local_load_call = LocalFakeModelClass.local_load_calls[0]
            self.assertEqual(local_load_call["device"], "cpu")
            self.assertEqual(
                set(local_load_call),
                {"ckpt_dir", "device"},
            )
            self.assertTrue(
                local_load_call["ckpt_dir"].samefile(snapshot),
                f"Expected the local loader to use {snapshot}, "
                f"got {local_load_call['ckpt_dir']}",
            )

    def test_generation_errors_use_the_standard_adapter_error(self):
        with TemporaryDirectory() as temp_folder:
            voice_file = Path(temp_folder) / "voice.wav"
            voice_file.touch()

            with patch.object(
                ChatterboxOriginalAdapter,
                "model_class",
                FailingGenerationModelClass,
            ):
                adapter = ChatterboxOriginalAdapter(device="cpu").load()
                adapter.prepare_voice(voice_file)

                with self.assertRaisesRegex(
                    SynthesisError,
                    "Chatterbox Original generation failed",
                ):
                    adapter.generate("Test sentence.", self.options)

                adapter.unload()

    def test_factory_exposes_only_the_four_requested_models(self):
        self.assertEqual(
            resolve_model_adapter_name("original", "en"),
            "original",
        )
        self.assertEqual(
            resolve_model_adapter_name("v3", "fr"),
            "v3",
        )
        self.assertIsInstance(
            create_tts_model_adapter("turbo", "en", "cpu"),
            ChatterboxTurboAdapter,
        )

        with self.assertRaises(ModelCompatibilityError):
            resolve_model_adapter_name("turbo", "fr")

        with self.assertRaises(ModelCompatibilityError):
            resolve_model_adapter_name("multilingual", "en")

    def test_installed_chatterbox_source_supports_v3_and_nano(self):
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS
        from chatterbox.tts_turbo import ChatterboxTurboTTS

        multilingual_parameters = inspect.signature(
            ChatterboxMultilingualTTS.from_pretrained
        ).parameters
        turbo_parameters = inspect.signature(
            ChatterboxTurboTTS.from_pretrained
        ).parameters

        self.assertIn("t3_model", multilingual_parameters)
        self.assertIn("nano", turbo_parameters)


if __name__ == "__main__":
    unittest.main()
