from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import torch

from modules.generator import VoiceGenerator


class PersistentGeneratorTests(unittest.TestCase):
    @staticmethod
    def _generator(chunks_folder, output_folder):
        generator = VoiceGenerator.__new__(VoiceGenerator)
        generator.chunks_folder = Path(chunks_folder)
        generator.output_folder = Path(output_folder)
        generator.output_format = "wav"
        generator.sample_rate = 24000
        return generator

    def test_chunk_is_replaced_atomically_before_completion_callback(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            chunks = root / "chunks"
            audio = root / "audio"
            chunks.mkdir()
            audio.mkdir()
            chunk = chunks / "chunk0001.txt"
            chunk.write_text("A short test.", encoding="utf-8")
            generator = self._generator(chunks, audio)
            events = []

            def fake_save(path, waveform, sample_rate, format):
                Path(path).write_bytes(b"complete wav")

            def before(chunk_file, output_file):
                events.append(("running", output_file.exists()))

            def after(chunk_file, output_file, elapsed, skipped):
                events.append(("complete", output_file.read_bytes(), skipped))

            with (
                patch.object(
                    generator,
                    "generate_chunk",
                    return_value=torch.zeros(1, 8),
                ),
                patch(
                    "modules.generator.output.torchaudio.save",
                    side_effect=fake_save,
                ),
            ):
                outputs = generator.run(
                    before_chunk=before,
                    after_chunk=after,
                )

            output = audio / "chunk0001.wav"
            self.assertEqual(outputs, [output])
            self.assertEqual(events[0], ("running", False))
            self.assertEqual(events[1], ("complete", b"complete wav", False))
            self.assertFalse(any(audio.glob("*.tmp.wav")))

    def test_failed_save_removes_partial_file_and_reports_failure(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            chunks = root / "chunks"
            audio = root / "audio"
            chunks.mkdir()
            audio.mkdir()
            chunk = chunks / "chunk0001.txt"
            chunk.write_text("A short test.", encoding="utf-8")
            generator = self._generator(chunks, audio)
            errors = []

            def failing_save(path, waveform, sample_rate, format):
                Path(path).write_bytes(b"partial")
                raise RuntimeError("mock disk failure")

            with (
                patch.object(
                    generator,
                    "generate_chunk",
                    return_value=torch.zeros(1, 8),
                ),
                patch(
                    "modules.generator.output.torchaudio.save",
                    side_effect=failing_save,
                ),
            ):
                with self.assertRaisesRegex(RuntimeError, "mock disk failure"):
                    generator.run(
                        on_chunk_error=(
                            lambda chunk_file, output_file, error:
                            errors.append(str(error))
                        ),
                    )

            self.assertEqual(errors, ["mock disk failure"])
            self.assertFalse((audio / "chunk0001.wav").exists())
            self.assertFalse(any(audio.iterdir()))


if __name__ == "__main__":
    unittest.main()
