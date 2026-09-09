from __future__ import annotations

import os
from pathlib import Path
import time
import uuid

import torchaudio
from tqdm import tqdm


class ChunkOutputWriter:
    """Generate chunk files and publish each audio file atomically."""

    def __init__(self, generator):
        self.generator = generator

    def run(
        self,
        chunk_files=None,
        output_folder=None,
        before_chunk=None,
        after_chunk=None,
        on_chunk_error=None,
    ):
        generator = self.generator
        if chunk_files is None:
            chunks = sorted(generator.chunks_folder.glob("chunk*.txt"))
        else:
            chunks = sorted(Path(chunk) for chunk in chunk_files)

        destination = Path(output_folder or generator.output_folder)
        destination.mkdir(parents=True, exist_ok=True)
        print(f"Found {len(chunks)} chunks")
        generated_outputs = []

        for index, chunk in enumerate(tqdm(chunks), start=1):
            output = destination / (
                chunk.stem + "." + generator.output_format
            )

            if before_chunk is not None:
                before_chunk(chunk, output)

            if output.is_file() and output.stat().st_size > 0:
                print(f"Skipping {output.name}")

                if after_chunk is not None:
                    after_chunk(chunk, output, 0.0, True)

                generated_outputs.append(output)
                continue

            print(f"Generating chunk {index}/{len(chunks)}")
            text = chunk.read_text(encoding="utf-8")
            start = time.time()
            temporary = output.parent / (
                f".{output.stem}.{uuid.uuid4().hex}.tmp."
                f"{generator.output_format}"
            )
            wav = None

            try:
                wav = generator.generate_chunk(text)
                torchaudio.save(
                    str(temporary),
                    wav,
                    generator.sample_rate,
                    format=generator.output_format,
                )

                with temporary.open("r+b") as saved_audio:
                    os.fsync(saved_audio.fileno())

                os.replace(temporary, output)
                elapsed = time.time() - start
                print(f"Saved {output.name} ({elapsed:.1f}s)")

                if after_chunk is not None:
                    after_chunk(chunk, output, elapsed, False)

                generated_outputs.append(output)
            except Exception as error:
                if on_chunk_error is not None:
                    on_chunk_error(chunk, output, error)

                raise
            finally:
                if temporary.exists():
                    temporary.unlink()

                if wav is not None:
                    del wav

                generator._release_cuda_memory()

        return generated_outputs
