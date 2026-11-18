from contextlib import redirect_stdout, redirect_stderr
from dataclasses import asdict
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
import wave

from modules.app_settings import SettingsRepository
from modules.config import PipelineConfig
from modules.pipeline import run_job
from modules.service import TTSHarnessService
from modules.subtitles import SpokenWord, render_player, render_srt, spoken_words


class SubtitleTests(unittest.TestCase):
    def test_word_times_and_exports_preserve_pauses_and_escape_html(self):
        result = {"chunks": [
            {"text": " Hello", "timestamp": (0.04, 0.42)},
            {"text": " <world>", "timestamp": (1.3, None)},
        ]}
        words = spoken_words(result, duration_ms=1800)
        self.assertEqual(words, [
            SpokenWord(" Hello", 40, 420), SpokenWord(" <world>", 1300, 1800),
        ])
        self.assertEqual(render_srt(words), (
            "1\n00:00:00,040 --> 00:00:00,420\nHello\n\n"
            "2\n00:00:01,300 --> 00:00:01,800\n<world>\n"
        ))
        html = render_player("a # b.wav", words)
        self.assertIn('src="a%20%23%20b.wav"', html)
        self.assertIn('data-start="1300" data-end="1800"> &lt;world&gt;', html)

    def test_job_publishes_both_subtitle_files_before_cleaning_chunk_artifacts(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            paths = SettingsRepository.for_testing(root).paths
            service = TTSHarnessService(paths)
            source = root / "chapter.txt"
            voice = root / "reference.wav"
            source.write_text("Written script.", encoding="utf-8")
            voice.write_bytes(b"voice fixture")
            manifest = service.store.create_job(
                scripts=(source,),
                settings=asdict(PipelineConfig(export_subtitles=True)),
                voice_file=voice,
                job_id="subtitle-fixture",
            )
            job_id = manifest["job_id"]
            script = manifest["scripts"][0]
            text_path = Path(script["chunks_directory"]) / "chunk0001.txt"
            audio_path = Path(script["audio_directory"]) / "chunk0001.wav"
            text = service.store.resolve_artifact(job_id, text_path)
            text.parent.mkdir(parents=True)
            text.write_text("Written script.", encoding="utf-8")
            output = service.store.resolve_artifact(job_id, script["output_path"])
            for wav_path in (service.store.resolve_artifact(job_id, audio_path), output):
                wav_path.parent.mkdir(parents=True)
                with wave.open(str(wav_path), "wb") as wav:
                    wav.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
                    wav.writeframes(b"\x01\x00" * 24000)
            script["chunks"] = [{
                "id": "chunk0001", "text_path": text_path.as_posix(),
                "audio_path": audio_path.as_posix(), "status": "complete",
            }]
            service.store.save(manifest)

            exporter = Mock()
            exporter.transcribe.return_value = [
                SpokenWord(" Actually", 50, 300), SpokenWord(" spoken.", 320, 750),
            ]
            with (
                patch("modules.pipeline.job_runner.SubtitleExporter", return_value=exporter),
                redirect_stdout(StringIO()), redirect_stderr(StringIO()),
            ):
                result = run_job(service.store, manifest, app_paths=paths)

            self.assertEqual(result, 0)
            exporter.transcribe.assert_called_once_with(output, "en")
            completed = service.load_job(job_id)
            [published] = service.output_paths(completed)
            srt, player = service.subtitle_paths(published)
            self.assertIn("Actually spoken.", srt.read_text(encoding="utf-8"))
            self.assertIn('data-start="320" data-end="750"> spoken.', player.read_text(encoding="utf-8"))
            self.assertEqual(completed["artifact_cleanup"]["status"], "complete")
            self.assertFalse(text.exists())
