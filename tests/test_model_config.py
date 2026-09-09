from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from modules.config import PipelineConfig


class ModelConfigTests(unittest.TestCase):
    def test_repository_defaults_use_current_original_model(self):
        defaults_file = (
            Path(__file__).resolve().parents[1]
            / "config.default.yaml"
        )

        config = PipelineConfig.from_file(defaults_file)

        self.assertEqual(config.model, "original")
        self.assertEqual(config.splitting_mode, "automatic")
        self.assertEqual(config.automatic_min_words, 20)
        self.assertEqual(config.automatic_max_words, 160)
        self.assertEqual(config.vram_safety_margin_mb, 1024)
        self.assertTrue(config.cpu_fallback)
        self.assertEqual(config.device_preference, "auto")

    def test_active_file_can_omit_model_and_inherit_the_default(self):
        with TemporaryDirectory() as temp_folder:
            folder = Path(temp_folder)
            defaults_file = folder / "defaults.yaml"
            active_file = folder / "active.yaml"

            defaults_file.write_text(
                "voice: test\nmodel: turbo\nlanguage: en\n",
                encoding="utf-8",
            )
            active_file.write_text(
                "voice: personal.wav\n",
                encoding="utf-8",
            )

            config = PipelineConfig.from_file(
                active_file,
                defaults_file=defaults_file,
            )

            self.assertEqual(config.model, "turbo")
            self.assertEqual(config.voice, "personal.wav")

    def test_model_names_are_normalized_and_validated(self):
        self.assertEqual(
            PipelineConfig(model=" V3 ").model,
            "v3",
        )

        with self.assertRaisesRegex(ValueError, "Config 'model'"):
            PipelineConfig(model="unsupported")

    def test_model_language_capabilities_are_validated(self):
        with self.assertRaisesRegex(
            ValueError,
            "Turbo does not support language 'fr'",
        ):
            PipelineConfig(model="turbo", language="fr")

        config = PipelineConfig(model="v3", language="fr")
        self.assertEqual(config.language, "fr")

    def test_top_k_is_validated(self):
        self.assertEqual(PipelineConfig(top_k=750).top_k, 750)

        with self.assertRaisesRegex(ValueError, "Config 'top_k'"):
            PipelineConfig(top_k=0)

        with self.assertRaisesRegex(ValueError, "Config 'top_k'"):
            PipelineConfig(top_k=1001)

    def test_generation_controls_reject_unstable_ranges(self):
        invalid_values = {
            "exaggeration": 1.01,
            "cfg_weight": 1.01,
            "temperature": 1.51,
            "repetition_penalty": 2.01,
            "min_p": 0.21,
            "top_p": 0.09,
        }

        for field, value in invalid_values.items():
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError, f"Config '{field}'"):
                    PipelineConfig(**{field: value})

    def test_resource_runtime_modes_are_normalized_and_validated(self):
        config = PipelineConfig(
            splitting_mode=" MANUAL ",
            device_preference=" CPU ",
            generation_max_words=200,
        )

        self.assertEqual(config.splitting_mode, "manual")
        self.assertEqual(config.device_preference, "cpu")
        self.assertEqual(config.generation_max_words, 200)

        with self.assertRaisesRegex(ValueError, "splitting_mode"):
            PipelineConfig(splitting_mode="guess")

        with self.assertRaisesRegex(ValueError, "device_preference"):
            PipelineConfig(device_preference="webgpu")

    def test_automatic_bounds_and_vram_margin_are_validated(self):
        with self.assertRaisesRegex(ValueError, "automatic_min_words"):
            PipelineConfig(
                automatic_min_words=100,
                automatic_max_words=50,
            )

        with self.assertRaisesRegex(ValueError, "vram_safety_margin_mb"):
            PipelineConfig(vram_safety_margin_mb=-1)

        self.assertEqual(
            PipelineConfig(vram_safety_margin_mb=0).vram_safety_margin_mb,
            0,
        )


if __name__ == "__main__":
    unittest.main()
