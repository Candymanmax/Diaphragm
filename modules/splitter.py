from pathlib import Path
import syntok.segmenter


class ScriptSplitter:
    def __init__(
        self,
        input_file,
        output_folder,
        target_words=50,
        min_words=15,
    ):
        self.input_file = Path(input_file)
        self.output_folder = Path(output_folder)
        self.target_words = target_words
        self.min_words = min_words

    def clean_text(self, text):
        text = text.replace("\r\n", "\n")
        text = text.replace("\t", " ")

        while "  " in text:
            text = text.replace("  ", " ")

        while "\n\n\n" in text:
            text = text.replace("\n\n\n", "\n\n")

        return text.strip()

    def split(self):

        self.output_folder.mkdir(parents=True, exist_ok=True)

        text = self.input_file.read_text(
            encoding="utf-8"
        )

        text = self.clean_text(text)

        document = syntok.segmenter.analyze(text)

        chunk = []
        chunk_words = 0
        chunk_number = 1

        for paragraph in document:

            for sentence in paragraph:

                sentence_text = "".join(
                    token.spacing + token.value
                    for token in sentence
                ).strip()

                sentence_words = len(sentence_text.split())

                if (
                    chunk_words + sentence_words
                    > self.target_words
                    and chunk_words >= self.min_words
                ):

                    output = self.output_folder / f"chunk{chunk_number:04d}.txt"

                    output.write_text(
                        "\n\n".join(chunk),
                        encoding="utf-8"
                    )

                    chunk_number += 1
                    chunk = []
                    chunk_words = 0

                chunk.append(sentence_text)
                chunk_words += sentence_words

        if chunk:

            output = self.output_folder / f"chunk{chunk_number:04d}.txt"

            output.write_text(
                "\n\n".join(chunk),
                encoding="utf-8"
            )

        print(f"Created {chunk_number} chunk(s)")