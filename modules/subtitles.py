"""Transcribe generated audio and export captions with a word-following player."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
import math
from pathlib import Path
from string import Template
from urllib.parse import quote


MODEL_ID = "openai/whisper-tiny"


@dataclass(frozen=True)
class SpokenWord:
    text: str
    start_ms: int
    end_ms: int


def subtitle_files(audio):
    audio = Path(audio)
    return audio.with_suffix(".srt"), audio.with_suffix(".subtitles.html")


def spoken_words(result, duration_ms):
    words = []
    end_ms = 0
    for chunk in result.get("chunks", []):
        text = chunk["text"]
        start, end = chunk["timestamp"]
        if (
            not text.strip() or start is None or not math.isfinite(start)
            or (end is not None and not math.isfinite(end))
        ):
            continue
        start_ms = max(end_ms, round(start * 1000))
        next_end = duration_ms if end is None else round(end * 1000)
        next_end = min(duration_ms, next_end)
        if next_end > start_ms:
            words.append(SpokenWord(text, start_ms, next_end))
            end_ms = next_end
    return words


def _timestamp(milliseconds):
    seconds, ms = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{ms:03d}"


def render_srt(words):
    groups = []
    group = []
    length = 0
    for word in words:
        if group and (
            length + len(word.text) > 76
            or word.end_ms - group[0].start_ms > 6000
            or word.start_ms - group[-1].end_ms > 600
        ):
            groups.append(group)
            group = []
            length = 0
        group.append(word)
        length += len(word.text)
    if group:
        groups.append(group)

    cues = []
    for index, group in enumerate(groups, start=1):
        start = _timestamp(group[0].start_ms)
        end = _timestamp(group[-1].end_ms)
        text = " ".join("".join(word.text for word in group).split())
        cues.append(f"{index}\n{start} --> {end}\n{text}\n")
    return "\n".join(cues)


_PLAYER = Template("""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$title</title>
<style>
  :root { color-scheme: light dark; }
  body { margin: 0 auto; max-width: 48rem; padding: 0 1.25rem;
         font: 1rem/1.6 system-ui, sans-serif; }
  header { position: sticky; top: 0; padding: 1rem 0; background: Canvas; }
  h1 { margin: 0 0 .75rem; font-size: 1.35rem; }
  audio { width: 100%; display: block; }
  main { padding: 1rem 0 3rem; font-size: 1.18rem; line-height: 1.9; }
  .word { scroll-margin-block: 9rem 2rem; border-radius: .18rem; }
  .current { background: #fde68a; color: #282011; }
</style>
</head>
<body>
<header><h1>$title</h1><audio controls preload="metadata" src="$audio"></audio></header>
<main aria-label="Transcript">$transcript</main>
<script>
const audio = document.querySelector('audio');
const words = Array.from(document.querySelectorAll('.word'));
const starts = words.map(word => Number(word.dataset.start));
const ends = words.map(word => Number(word.dataset.end));
let current = -1;
let frame = 0;

function updateWord() {
  const time = audio.currentTime * 1000;
  let low = 0;
  let high = words.length;
  while (low < high) {
    const middle = Math.floor((low + high) / 2);
    if (starts[middle] <= time) low = middle + 1;
    else high = middle;
  }
  const index = low - 1;
  const next = index >= 0 && time < ends[index] && !audio.ended ? index : -1;
  if (next === current) return;
  if (current >= 0) words[current].classList.remove('current');
  current = next;
  if (current >= 0) {
    words[current].classList.add('current');
    words[current].scrollIntoView({block: 'nearest'});
  }
}

function tick() {
  updateWord();
  if (!audio.paused && !audio.ended) frame = requestAnimationFrame(tick);
}

audio.addEventListener('play', () => {
  cancelAnimationFrame(frame);
  tick();
});
for (const event of ['timeupdate', 'seeking', 'seeked', 'pause', 'ended']) {
  audio.addEventListener(event, updateWord);
}
</script>
</body>
</html>
""")


def render_player(audio, words):
    audio = Path(audio)
    # Preserve the decoder's word spacing and punctuation, including languages
    # that do not put a space between every word.
    transcript = "".join(
        f'<span class="word" data-start="{word.start_ms}" data-end="{word.end_ms}">'
        f'{escape(word.text)}</span>'
        for word in words
    )
    return _PLAYER.substitute(
        title=escape(audio.stem), audio=quote(audio.name), transcript=transcript
    )


class SubtitleExporter:
    """Reuse a local speech recognizer for all outputs in one job."""

    def __init__(self, cache_dir):
        self.cache_dir = cache_dir
        self.recognizer = None

    def _load(self):
        from transformers.models.whisper.modeling_whisper import WhisperForConditionalGeneration
        from transformers.models.whisper.processing_whisper import WhisperProcessor
        from transformers.pipelines import pipeline

        model = WhisperForConditionalGeneration.from_pretrained(
            MODEL_ID, cache_dir=self.cache_dir, use_safetensors=True
        )
        processor = WhisperProcessor.from_pretrained(MODEL_ID, cache_dir=self.cache_dir)
        return pipeline(
            "automatic-speech-recognition",
            model=model,
            tokenizer=processor.tokenizer,
            feature_extractor=processor.feature_extractor,
            device=-1,
        )

    def transcribe(self, audio, language):
        import soundfile as sf

        waveform, sample_rate = sf.read(audio, dtype="float32", always_2d=True)
        duration_ms = round(len(waveform) * 1000 / sample_rate)
        if self.recognizer is None:
            self.recognizer = self._load()
        result = self.recognizer(
            {"raw": waveform.mean(axis=1), "sampling_rate": sample_rate},
            return_timestamps="word",
            generate_kwargs={"task": "transcribe", "language": language},
        )
        words = spoken_words(result, duration_ms)
        if not words:
            raise RuntimeError("Subtitle transcription returned no timed words.")
        return words
