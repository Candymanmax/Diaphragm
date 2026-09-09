from pathlib import Path
import os
import random
import uuid
import torch
import torchaudio


class AudioMerger:

    def __init__(
        self,
        input_folder,
        chunks_folder,
        output_file="final.wav",
        min_silence_ms=100,
        max_silence_ms=250,
        pause_mean_ms=220.0,
        pause_std_ms=50.0,
        sample_rate=24000,
        output_format="wav",
        cleanup_inputs=False,
    ):

        self.input_folder = Path(input_folder)
        self.chunks_folder = Path(chunks_folder)

        requested_output = Path(output_file)

        if requested_output.parent == Path("."):
            requested_output = Path("final") / requested_output

        self.output_folder = requested_output.parent
        self.output_folder.mkdir(
            parents=True,
            exist_ok=True
        )

        self.output_file = requested_output

        self.min_silence_ms = min_silence_ms
        self.max_silence_ms = max_silence_ms
        self.pause_mean_ms = pause_mean_ms
        self.pause_std_ms = pause_std_ms
        self.sample_rate = sample_rate
        self.output_format = output_format.lower().lstrip(".")
        self.cleanup_inputs = cleanup_inputs


    def create_silence(self):

        silence_ms = max(
            self.min_silence_ms,
            min(
                self.max_silence_ms,
                random.gauss(
                    self.pause_mean_ms,
                    self.pause_std_ms
                )
            )
        )

        samples = int(
            self.sample_rate *
            silence_ms / 1000
        )

        return torch.zeros(
            1,
            samples
        )


    def cleanup(self):

        deleted = 0

        for wav_file in self.input_folder.glob(
            f"chunk*.{self.output_format}"
        ):
            try:
                wav_file.unlink()
                print(f"Deleted {wav_file.name}")
                deleted += 1
            except Exception as e:
                print(f"Failed to delete {wav_file.name}: {e}")

        for txt_file in self.chunks_folder.glob("chunk*.txt"):
            try:
                txt_file.unlink()
                print(f"Deleted {txt_file.name}")
                deleted += 1
            except Exception as e:
                print(f"Failed to delete {txt_file.name}: {e}")

        print(f"Cleanup complete. Deleted {deleted} files.")


    def merge(self):

        files = sorted(
            self.input_folder.glob(
                f"chunk*.{self.output_format}"
            )
        )

        if not files:
            raise RuntimeError(
                "No audio files found"
            )

        print(
            f"Merging {len(files)} files"
        )

        audio_parts = []

        for index, file in enumerate(files):

            print(
                f"Adding {file.name}"
            )

            wav, sr = torchaudio.load(file)

            if sr != self.sample_rate:
                wav = torchaudio.functional.resample(
                    wav,
                    sr,
                    self.sample_rate
                )

            audio_parts.append(wav)

            if index < len(files) - 1:

                silence = self.create_silence()

                print(
                    f"Adding {silence.shape[1] / self.sample_rate * 1000:.0f} ms silence"
                )

                audio_parts.append(silence)

        final_audio = torch.cat(
            audio_parts,
            dim=1
        )

        temporary = self.output_folder / (
            f".{self.output_file.stem}.{uuid.uuid4().hex}.tmp."
            f"{self.output_format}"
        )

        try:
            torchaudio.save(
                str(temporary),
                final_audio,
                self.sample_rate,
                format=self.output_format,
            )

            with temporary.open("r+b") as saved_audio:
                os.fsync(saved_audio.fileno())

            os.replace(temporary, self.output_file)
        finally:
            if temporary.exists():
                temporary.unlink()

        print(
            f"Saved {self.output_file}"
        )

        if self.cleanup_inputs:
            self.cleanup()

        return self.output_file
