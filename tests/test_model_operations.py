"""Tests for source and packaged model-maintenance dispatch."""

from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import types
import unittest
from unittest.mock import patch

import desktop_gui
from modules.model_operations import (
    model_download_arguments,
    model_inventory_arguments,
)


class ModelOperationTests(unittest.TestCase):
    def test_packaged_smoke_check_imports_both_native_runtime_modules(self):
        torch = type("Torch", (), {"__version__": "2.6.0+cpu"})()
        torchaudio = type("TorchAudio", (), {"__version__": "2.6.0+cpu"})()

        with patch.dict(
            sys.modules,
            {"torch": torch, "torchaudio": torchaudio},
        ):
            summary = desktop_gui._smoke_test_runtime_imports()

        self.assertEqual(
            summary,
            "torch=2.6.0+cpu torchaudio=2.6.0+cpu",
        )

    def test_packaged_smoke_check_imports_the_generation_adapter(self):
        fake_chatterbox = types.ModuleType("chatterbox")
        fake_chatterbox.ChatterboxTTS = type("ChatterboxTTS", (), {})
        fake_perth = types.ModuleType("perth")
        calls = []
        class PerthImplicitWatermarker:
            def __init__(self):
                calls.append("loaded")
        fake_perth.PerthImplicitWatermarker = PerthImplicitWatermarker

        with patch.dict(sys.modules, {"chatterbox": fake_chatterbox, "perth": fake_perth}):
            summary = desktop_gui._smoke_test_generation_imports()

        self.assertEqual(calls, ["loaded"])
        self.assertEqual(summary, "chatterbox=ChatterboxTTS watermarker=PerthImplicitWatermarker")

    def test_model_commands_switch_between_module_and_packaged_dispatch(self):
        with TemporaryDirectory() as temporary:
            cache_root = Path(temporary)

            for frozen, expected_prefix in (
                (False, ("-m", "modules.model_download")),
                (True, ("--model-download",)),
            ):
                with self.subTest(frozen=frozen), patch.object(
                    sys,
                    "frozen",
                    frozen,
                    create=True,
                ):
                    arguments = model_download_arguments(
                        " Nano ",
                        cache_root,
                        operation=" Repair ",
                    )

                self.assertEqual(arguments[:len(expected_prefix)], expected_prefix)
                self.assertIn("nano", arguments)
                self.assertEqual(arguments[-2:], ("--operation", "repair"))
                configured_cache = Path(
                    arguments[arguments.index("--cache-root") + 1]
                )
                self.assertTrue(configured_cache.samefile(cache_root))

            for frozen, expected_prefix in (
                (False, ("-m", "modules.model_inventory")),
                (True, ("--model-inventory",)),
            ):
                with self.subTest(frozen=frozen), patch.object(
                    sys,
                    "frozen",
                    frozen,
                    create=True,
                ):
                    arguments = model_inventory_arguments(
                        " Verify ",
                        " Original ",
                        cache_root,
                    )

                self.assertEqual(arguments[:len(expected_prefix)], expected_prefix)
                self.assertIn("verify", arguments)
                self.assertIn("original", arguments)
                configured_cache = Path(
                    arguments[arguments.index("--cache-root") + 1]
                )
                self.assertTrue(configured_cache.samefile(cache_root))

    def test_desktop_entry_dispatches_model_commands_before_starting_the_gui(self):
        cases = (
            ("--model-download", "_run_model_download"),
            ("--model-inventory", "_run_model_inventory"),
        )

        for flag, dispatcher_name in cases:
            payload = ["nano", "--cache-root", "C:/model-cache"]
            with self.subTest(flag=flag), patch.object(
                desktop_gui,
                dispatcher_name,
                return_value=17,
            ) as dispatcher:
                result = desktop_gui.main([flag, *payload])

            self.assertEqual(result, 17)
            dispatcher.assert_called_once_with(payload)


if __name__ == "__main__":
    unittest.main()
