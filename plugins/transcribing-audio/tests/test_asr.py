from __future__ import annotations

from pathlib import Path

import pytest

from audio_transcriber.asr import Interval, deduplicate_overlap, merge_chunk_results, offset_words
from audio_transcriber.models import ASRChunkResult, AsrSegment, AudioChunk, AudioWindow, Word


def _chunk(identifier: str, start: float, end: float) -> AudioChunk:
    return AudioChunk(
        window=AudioWindow(identifier, start, end, 0 if start == 0 else 2, 0 if end == 20 else 2),
        path=Path(f"/private/tmp/{identifier}.flac"),
        size_bytes=1,
        sha256="a" * 64,
    )


def _result(
    identifier: str, start: float, end: float, words: tuple[tuple[float, float, str], ...]
) -> ASRChunkResult:
    chunk = _chunk(identifier, start, end)
    return ASRChunkResult(
        chunk=chunk,
        backend="local",
        model="test",
        language="en",
        segments=(
            AsrSegment(
                start_s=words[0][0],
                end_s=words[-1][1],
                text=" ".join(item[2] for item in words),
                words=tuple(
                    Word(word_start, word_end, text, None, identifier)
                    for word_start, word_end, text in words
                ),
                average_log_probability=None,
                no_speech_probability=None,
            ),
        )
        if words
        else (),
    )


def test_offset_words_preserves_chunk_provenance_and_absolute_timestamps() -> None:
    result = _result("chunk-0001", 8, 18, ((0.5, 1.0, "hello"),))

    assert offset_words(result) == (Word(8.5, 9.0, "hello", None, "chunk-0001"),)


def test_deduplicate_overlap_handles_case_and_punctuation_variants() -> None:
    left = (Word(8.0, 8.4, "Hello", None, "left"), Word(8.5, 9.0, "world", None, "left"))
    right = (
        Word(8.5, 9.0, "WORLD!", None, "right"),
        Word(9.1, 9.5, "again", None, "right"),
    )

    assert deduplicate_overlap(left, right, Interval(8, 10)) == (
        Word(9.1, 9.5, "again", None, "right"),
    )


def test_deduplicate_overlap_removes_only_timestamp_identical_fallback_words() -> None:
    left = (Word(8.0, 8.5, "same", None, "left"),)
    right = (Word(8.1, 8.6, "same", None, "right"), Word(9.0, 9.5, "different", None, "right"))

    assert deduplicate_overlap(left, right, Interval(8, 10)) == (right[1],)


def test_merge_handles_three_chunks_and_silent_chunk() -> None:
    first = _result("chunk-0000", 0, 10, ((8.0, 8.5, "one"), (8.5, 9.0, "two")))
    second = _result("chunk-0001", 8, 18, ((0.5, 1.0, "two"), (1.0, 1.5, "three")))
    third = _result("chunk-0002", 16, 20, ())

    words = merge_chunk_results((first, second, third))

    assert [word.text for word in words] == ["one", "two", "three"]
    assert [word.source_chunk for word in words] == ["chunk-0000", "chunk-0000", "chunk-0001"]


def test_merge_keeps_non_matching_overlap_and_rejects_backwards_backend_words() -> None:
    first = _result("chunk-0000", 0, 10, ((8.0, 8.5, "one"),))
    second = _result("chunk-0001", 8, 18, ((0.0, 0.5, "other"),))

    assert [word.text for word in merge_chunk_results((first, second))] == ["one", "other"]
    chunk = _chunk("chunk-0001", 8, 18)
    backwards = ASRChunkResult(
        chunk=chunk,
        backend="local",
        model="test",
        language="en",
        segments=(
            AsrSegment(2, 2.5, "late", (Word(2, 2.5, "late", None, chunk.window.id),), None, None),
            AsrSegment(
                1, 1.5, "early", (Word(1, 1.5, "early", None, chunk.window.id),), None, None
            ),
        ),
    )
    with pytest.raises(ValueError, match="chronological"):
        merge_chunk_results((first, backwards))
