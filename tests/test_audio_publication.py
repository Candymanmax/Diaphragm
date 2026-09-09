from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import os
import unittest
import warnings

import numpy as np
import soundfile as sf

from modules.files import AtomicReplaceError, replace_with_retry
from modules.normalizer import AudioNormalizer, PEAK_LIMIT_DBFS


class AtomicPublicationTests(unittest.TestCase):
    def test_atomic_replace_retries_a_short_windows_file_lock(self):
        with TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = folder / "new.tmp"
            destination = folder / "output.wav"
            source.write_bytes(b"new output")
            destination.write_bytes(b"old output")
            real_replace = os.replace
            attempts = 0

            def flaky_replace(source_path, destination_path):
                nonlocal attempts
                attempts += 1

                if attempts < 3:
                    raise PermissionError("temporarily locked")

                real_replace(source_path, destination_path)

            with (
                patch("modules.files.os.replace", side_effect=flaky_replace),
                patch("modules.files.time.sleep") as sleep,
            ):
                replace_with_retry(source, destination)

            self.assertEqual(destination.read_bytes(), b"new output")
            self.assertEqual(attempts, 3)
            self.assertEqual(sleep.call_count, 2)

    def test_atomic_replace_reports_an_actionable_persistent_lock(self):
        with TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = folder / "new.tmp"
            destination = folder / "output.wav"
            source.write_bytes(b"new output")

            with (
                patch(
                    "modules.files.os.replace",
                    side_effect=PermissionError("locked"),
                ),
                patch("modules.files.time.sleep"),
                self.assertRaisesRegex(
                    AtomicReplaceError,
                    "Stop playback.*OneDrive.*Retry failed",
                ),
            ):
                replace_with_retry(source, destination, attempts=2)

            self.assertTrue(source.exists())

    def test_loudness_normalization_limits_clipping_peaks(self):
        with TemporaryDirectory() as temporary:
            folder = Path(temporary)
            source = folder / "input.wav"
            output = folder / "output.wav"
            rate = 24000
            time_values = np.arange(rate * 2) / rate
            audio = 0.001 * np.sin(2 * np.pi * 220 * time_values)
            audio[rate] = 1.0
            sf.write(source, audio, rate, subtype="FLOAT")

            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                AudioNormalizer(source, output, target_lufs=-14).normalize()

            normalized, _ = sf.read(output)
            peak_limit = 10.0 ** (PEAK_LIMIT_DBFS / 20.0)
            self.assertLessEqual(
                float(np.max(np.abs(normalized))),
                peak_limit + 1e-4,
            )
            self.assertFalse(
                any("clipped samples" in str(item.message) for item in caught)
            )


if __name__ == "__main__":
    unittest.main()
