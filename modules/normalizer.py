from pathlib import Path
import math
import os
import uuid

import numpy as np
import pyloudnorm as pyln
import soundfile as sf

from modules.files import replace_with_retry


PEAK_LIMIT_DBFS = -1.0


class AudioNormalizer:
    def __init__(self, input_file, output_file, target_lufs=-14):
        self.input_file = Path(input_file)
        self.output_file = Path(output_file)
        self.target_lufs = target_lufs

    def normalize(self):
        audio, rate = sf.read(self.input_file)

        if not np.size(audio):
            raise ValueError("Cannot normalize an empty audio file")

        meter = pyln.Meter(rate)
        loudness = float(meter.integrated_loudness(audio))

        if not math.isfinite(loudness):
            raise ValueError(
                "Cannot normalize silent audio because its loudness is undefined"
            )

        gain_db = float(self.target_lufs) - loudness
        normalized = np.asarray(audio, dtype=np.float64) * (
            10.0 ** (gain_db / 20.0)
        )
        peak = float(np.max(np.abs(normalized)))
        peak_limit = 10.0 ** (PEAK_LIMIT_DBFS / 20.0)
        peak_limited = peak > peak_limit

        if peak_limited:
            normalized *= peak_limit / peak

        measured_lufs = float(meter.integrated_loudness(normalized))
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.output_file.parent / (
            f".{self.output_file.stem}.{uuid.uuid4().hex}.tmp"
            f"{self.output_file.suffix}"
        )

        try:
            sf.write(temporary, normalized, rate)

            with temporary.open("r+b") as saved_audio:
                os.fsync(saved_audio.fileno())

            replace_with_retry(temporary, self.output_file)
        finally:
            if temporary.exists():
                temporary.unlink()

        if peak_limited:
            print(
                f"Normalized toward {self.target_lufs} LUFS; limited peaks "
                f"to {PEAK_LIMIT_DBFS:.1f} dBFS (result {measured_lufs:.1f} LUFS)"
            )
        else:
            print(f"Normalized to {measured_lufs:.1f} LUFS")
