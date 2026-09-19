"""Pure helpers for bounded, semantically complete speech synthesis."""

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
import unicodedata

SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?。！？])\s+")
BREAK_CHARACTERS = frozenset(",，;；:：、")


@dataclass(frozen=True)
class SpeechVerification:
    passed: bool
    similarity: float
    tail_similarity: float


def compact_speech_text(text: str) -> str:
    """Normalize differences that do not change whether the ending was spoken."""
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return "".join(character for character in normalized if character.isalnum())


def _split_long_part(part: str, max_chars: int) -> list[str]:
    chunks: list[str] = []
    remaining = part.strip()
    while len(remaining) > max_chars:
        window = remaining[: max_chars + 1]
        punctuation_candidates = [
            index + 1
            for index, character in enumerate(window[:max_chars])
            if character in BREAK_CHARACTERS
        ]
        whitespace_candidates = [
            index + 1
            for index, character in enumerate(window[:max_chars])
            if character.isspace()
        ]
        useful = [
            candidate for candidate in punctuation_candidates if candidate >= max_chars // 2
        ] or [
            candidate for candidate in whitespace_candidates if candidate >= max_chars // 2
        ]
        boundary = useful[-1] if useful else max_chars
        chunk = remaining[:boundary].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[boundary:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


def segment_speech_text(text: str, *, max_chars: int, max_segments: int) -> list[str]:
    """Split at natural boundaries without dropping any non-whitespace content."""
    if max_chars < 1 or max_segments < 1:
        raise ValueError("Speech segmentation limits must be positive")
    stripped = text.strip()
    if not stripped:
        raise ValueError("Speech text must not be empty")

    natural_parts: list[str] = []
    for paragraph in re.split(r"\n+", stripped):
        for sentence in SENTENCE_BOUNDARY.split(paragraph.strip()):
            if sentence.strip():
                natural_parts.extend(_split_long_part(sentence, max_chars))

    segments: list[str] = []
    for part in natural_parts:
        combined = f"{segments[-1]} {part}" if segments else part
        if segments and len(combined) <= max_chars:
            segments[-1] = combined
        else:
            segments.append(part)
    if len(segments) > max_segments:
        raise ValueError("Speech requires too many segments")
    if compact_speech_text("".join(segments)) != compact_speech_text(stripped):
        raise ValueError("Speech segmentation changed the text")
    return segments


def verify_spoken_text(
    expected: str,
    transcript: str,
    *,
    min_similarity: float,
    min_tail_similarity: float,
    tail_chars: int,
) -> SpeechVerification:
    """Require broad coverage and a matching ending while tolerating STT spacing."""
    expected_compact = compact_speech_text(expected)
    transcript_compact = compact_speech_text(transcript)
    if not expected_compact or not transcript_compact:
        return SpeechVerification(False, 0.0, 0.0)

    similarity = SequenceMatcher(None, expected_compact, transcript_compact).ratio()
    compared_tail_chars = min(max(1, tail_chars), len(expected_compact))
    expected_tail = expected_compact[-compared_tail_chars:]
    transcript_tail = transcript_compact[-compared_tail_chars:]
    tail_similarity = SequenceMatcher(None, expected_tail, transcript_tail).ratio()
    return SpeechVerification(
        similarity >= min_similarity and tail_similarity >= min_tail_similarity,
        similarity,
        tail_similarity,
    )
