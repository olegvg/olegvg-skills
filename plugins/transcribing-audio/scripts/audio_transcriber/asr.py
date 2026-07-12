"""Backend-neutral word offsetting and deterministic chunk-overlap merging."""

from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

from .models import ASRChunkResult, Word

_MAX_MATCH_WORDS = 20
_MAX_MIDPOINT_DELTA_S = 0.75


@dataclass(frozen=True, slots=True)
class Interval:
    start_s: float
    end_s: float

    def __post_init__(self) -> None:
        if self.end_s < self.start_s:
            raise ValueError("overlap interval is inverted")

    def contains_midpoint(self, word: Word) -> bool:
        midpoint = (word.start_s + word.end_s) / 2
        return self.start_s <= midpoint <= self.end_s


def _normalized_token(text: str) -> str:
    start = 0
    end = len(text)
    while start < end and unicodedata.category(text[start]).startswith("P"):
        start += 1
    while end > start and unicodedata.category(text[end - 1]).startswith("P"):
        end -= 1
    return text[start:end].casefold()


def _validate_chronological(words: Sequence[Word]) -> None:
    previous_start = -1.0
    previous_end = -1.0
    for word in words:
        if word.start_s < previous_start or word.end_s < previous_end:
            raise ValueError("ASR backend words are not chronological")
        previous_start = word.start_s
        previous_end = word.end_s


def offset_words(result: ASRChunkResult) -> tuple[Word, ...]:
    """Translate one chunk's relative words to source-audio offsets."""
    relative_words = tuple(word for segment in result.segments for word in segment.words)
    _validate_chronological(relative_words)
    offset = result.chunk.window.start_s
    return tuple(
        Word(
            start_s=word.start_s + offset,
            end_s=word.end_s + offset,
            text=word.text,
            confidence=word.confidence,
            source_chunk=result.chunk.window.id,
        )
        for word in relative_words
    )


def _iou(left: Word, right: Word) -> float:
    intersection = max(0.0, min(left.end_s, right.end_s) - max(left.start_s, right.start_s))
    union = max(left.end_s, right.end_s) - min(left.start_s, right.start_s)
    return 0.0 if union <= 0 else intersection / union


def _is_match(left: Word, right: Word) -> bool:
    return (
        _normalized_token(left.text) == _normalized_token(right.text)
        and _normalized_token(left.text) != ""
        and abs((left.start_s + left.end_s - right.start_s - right.end_s) / 2)
        <= _MAX_MIDPOINT_DELTA_S
    )


def deduplicate_overlap(
    left: Sequence[Word], right: Sequence[Word], overlap: Interval
) -> tuple[Word, ...]:
    """Drop only repeated leading words from the right independent ASR window."""
    _validate_chronological(left)
    _validate_chronological(right)
    left_overlap = tuple(word for word in left if overlap.contains_midpoint(word))
    right_overlap_length = 0
    for word in right:
        if not overlap.contains_midpoint(word):
            break
        right_overlap_length += 1
    right_overlap = right[:right_overlap_length]
    maximum = min(_MAX_MATCH_WORDS, len(left_overlap), len(right_overlap))
    for size in range(maximum, 0, -1):
        left_suffix = left_overlap[-size:]
        right_prefix = right_overlap[:size]
        if all(
            _is_match(left_word, right_word)
            for left_word, right_word in zip(left_suffix, right_prefix)
        ):
            return tuple(right[size:])
    deduplicated: list[Word] = []
    for word in right:
        if overlap.contains_midpoint(word) and any(
            _normalized_token(word.text) == _normalized_token(existing.text)
            and _normalized_token(word.text) != ""
            and _iou(existing, word) >= 0.5
            for existing in left_overlap
        ):
            continue
        deduplicated.append(word)
    return tuple(deduplicated)


def merge_chunk_results(results: Sequence[ASRChunkResult]) -> tuple[Word, ...]:
    """Merge ordered local chunks without conditionally priming later windows."""
    if not results:
        return ()
    previous_chunk_start = -1.0
    merged: tuple[Word, ...] = ()
    previous_result: ASRChunkResult | None = None
    for result in results:
        window = result.chunk.window
        if window.start_s < previous_chunk_start:
            raise ValueError("ASR chunk results must be ordered by their planned windows")
        previous_chunk_start = window.start_s
        current = offset_words(result)
        if previous_result is not None:
            previous_window = previous_result.chunk.window
            overlap = Interval(
                max(previous_window.start_s, window.start_s),
                min(previous_window.end_s, window.end_s),
            )
            if overlap.end_s >= overlap.start_s:
                current = deduplicate_overlap(merged, current, overlap)
        merged += current
        previous_result = result
    _validate_chronological(merged)
    return merged
