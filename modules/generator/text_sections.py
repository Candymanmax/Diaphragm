from __future__ import annotations

from collections import deque

import syntok.segmenter


def sentence_units(text):
    """Split text into sentence-sized units with a safe plain-text fallback."""
    text = str(text).strip()

    if not text:
        return []

    try:
        document = syntok.segmenter.analyze(text)
        sentences = [
            "".join(
                token.spacing + token.value
                for token in sentence
            ).strip()
            for paragraph in document
            for sentence in paragraph
        ]
    except Exception:
        sentences = []

    return [sentence for sentence in sentences if sentence] or [text]


def take_section(units, max_words):
    """Consume one bounded section from a deque of sentence units."""
    section = []
    section_words = 0

    while units:
        sentence = units[0].strip()
        words = sentence.split()

        if not words:
            units.popleft()
            continue

        if len(words) > max_words:
            if section:
                break

            units.popleft()
            section = words[:max_words]
            remainder = words[max_words:]

            if remainder:
                units.appendleft(" ".join(remainder))

            section_words = len(section)
            break

        if section and section_words + len(words) > max_words:
            break

        units.popleft()
        section.append(sentence)
        section_words += len(words)

    return " ".join(section).strip()


def split_text(text, max_words):
    """Split text into word-bounded sections while preserving sentences."""
    units = deque(sentence_units(text))
    parts = []

    while units:
        part = take_section(units, int(max_words))

        if not part:
            break

        parts.append(part)

    return parts
