from dataclasses import FrozenInstanceError
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from modules.adapters.base import GenerationOptions
from modules.model_download import install_model
from modules.adapters.registry import (
    CapabilityValidationError,
    MODEL_ADAPTER_NAMES,
    MODEL_CAPABILITIES,
    MODEL_DOWNLOAD_FILES,
    PARALINGUISTIC_EVENT_TAGS,
    format_model_capabilities,
    get_model_capabilities,
    model_id_from_display_name,
    model_is_installed,
    supported_generation_options,
    validate_model_configuration,
)


class ModelCapabilityTests(unittest.TestCase):
    def test_registry_contains_exactly_the_selectable_models(self):
        self.assertEqual(
            MODEL_ADAPTER_NAMES,
            ("original", "turbo", "v3", "nano"),
        )
        self.assertEqual(
            tuple(MODEL_CAPABILITIES),
            MODEL_ADAPTER_NAMES,
        )

    def test_capability_records_are_immutable(self):
        original = get_model_capabilities("original")

        with self.assertRaises(FrozenInstanceError):
            original.display_name = "Changed"

        with self.assertRaises(TypeError):
            MODEL_CAPABILITIES["original"] = original

    def test_languages_and_devices_are_validated_before_loading(self):
        self.assertEqual(
            validate_model_configuration("original", "en").model_id,
            "original",
        )
        self.assertEqual(
            validate_model_configuration(
                "v3",
                "fr",
                device="cuda",
            ).model_id,
            "v3",
        )

        with self.assertRaisesRegex(
            CapabilityValidationError,
            "does not support language 'fr'",
        ):
            validate_model_configuration("turbo", "fr")

        with self.assertRaisesRegex(
            CapabilityValidationError,
            "does not support device 'webgpu'",
        ):
            validate_model_configuration(
                "v3",
                "en",
                device="webgpu",
            )

    def test_supported_controls_filter_model_requests(self):
        options = GenerationOptions(
            exaggeration=0.7,
            cfg_weight=0.3,
            temperature=0.75,
            repetition_penalty=1.1,
            min_p=0.08,
            top_p=0.9,
            top_k=750,
        )

        original_options = supported_generation_options(
            "original",
            options,
        )
        turbo_options = supported_generation_options("turbo", options)

        self.assertNotIn("top_k", original_options)
        self.assertIn("exaggeration", original_options)
        self.assertEqual(turbo_options["top_k"], 750)
        self.assertNotIn("exaggeration", turbo_options)
        self.assertNotIn("cfg_weight", turbo_options)
        self.assertNotIn("min_p", turbo_options)

    def test_event_tags_are_declared_only_for_turbo_and_nano(self):
        self.assertFalse(
            get_model_capabilities("original").supports_event_tags
        )
        self.assertFalse(get_model_capabilities("v3").supports_event_tags)

        for model_id in ("turbo", "nano"):
            capabilities = get_model_capabilities(model_id)
            self.assertEqual(
                capabilities.event_tags,
                PARALINGUISTIC_EVENT_TAGS,
            )
            self.assertIn("[cough]", capabilities.event_tags)
            self.assertIn("[laugh]", capabilities.event_tags)

    def test_display_mapping_and_readable_summary(self):
        self.assertEqual(
            model_id_from_display_name("Multilingual V3"),
            "v3",
        )
        self.assertEqual(model_id_from_display_name("nano"), "nano")

        summary = format_model_capabilities("nano", multiline=True)
        self.assertIn("110M", summary)
        self.assertIn("recommended: CPU", summary)
        self.assertIn("[cough]", summary)
        self.assertIn("longer than 5 seconds", summary)

    def test_cached_files_distinguish_models_sharing_a_repository(self):
        with TemporaryDirectory() as temporary:
            hub = Path(temporary)
            snapshot = (
                hub
                / "models--ResembleAI--chatterbox"
                / "snapshots"
                / "revision"
            )
            snapshot.mkdir(parents=True)
            for filename in MODEL_DOWNLOAD_FILES["original"][1]:
                (snapshot / filename).write_bytes(b"cached")

            self.assertTrue(model_is_installed("original", hub))
            self.assertFalse(model_is_installed("v3", hub))
            self.assertFalse(model_is_installed("turbo", hub))

            for filename in MODEL_DOWNLOAD_FILES["v3"][1]:
                (snapshot / filename).write_bytes(b"cached")

            self.assertTrue(model_is_installed("v3", hub))

    def test_model_installer_downloads_only_the_selected_file_set(self):
        with TemporaryDirectory() as temporary:
            hub = Path(temporary) / "models" / "huggingface" / "hub"

            def fake_download(**kwargs):
                snapshot = (
                    Path(kwargs["cache_dir"])
                    / "models--ResembleAI--chatterbox-turbo"
                    / "snapshots"
                    / "revision"
                )
                snapshot.mkdir(parents=True)
                for filename in kwargs["allow_patterns"]:
                    (snapshot / filename).write_bytes(b"cached")
                return str(snapshot)

            with patch(
                "modules.model_download.snapshot_download",
                side_effect=fake_download,
            ) as download:
                install_model("turbo", hub)

            arguments = download.call_args.kwargs
            self.assertEqual(arguments["repo_id"], "ResembleAI/chatterbox-turbo")
            self.assertEqual(
                tuple(arguments["allow_patterns"]),
                MODEL_DOWNLOAD_FILES["turbo"][1],
            )
            self.assertTrue(
                model_is_installed(
                    "turbo",
                    hub,
                )
            )

    def test_model_installer_retries_known_xet_failures(self):
        import huggingface_hub.constants as hf_constants

        with TemporaryDirectory() as temporary:
            hub = Path(temporary) / "models" / "huggingface" / "hub"
            calls = []

            def fake_download(**kwargs):
                calls.append(bool(hf_constants.HF_HUB_DISABLE_XET))

                if len(calls) == 1:
                    raise RuntimeError("hf_xet failed to decode a hash")

                snapshot = (
                    Path(kwargs["cache_dir"])
                    / "models--ResembleAI--chatterbox-turbo"
                    / "snapshots"
                    / "revision"
                )
                snapshot.mkdir(parents=True)
                for filename in kwargs["allow_patterns"]:
                    (snapshot / filename).write_bytes(b"cached")
                return str(snapshot)

            with (
                patch.object(hf_constants, "HF_HUB_DISABLE_XET", False),
                patch(
                    "modules.model_download.snapshot_download",
                    side_effect=fake_download,
                ) as download,
            ):
                install_model("turbo", hub)

            self.assertEqual(download.call_count, 2)
            self.assertEqual(calls, [False, True])


if __name__ == "__main__":
    unittest.main()
