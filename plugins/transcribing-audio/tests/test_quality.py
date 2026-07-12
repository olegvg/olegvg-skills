from __future__ import annotations

from pathlib import Path

import pytest

from audio_transcriber.quality import (
    QualityPolicy,
    RecoveryOptions,
    UnresolvedQualityError,
    evaluate_asr,
    recover_failed_chunks,
)
from audio_transcriber.models import ASRChunkResult, AsrSegment, AudioChunk, AudioWindow, Word


def _chunk(identifier: str, start: float = 0, end: float = 10) -> AudioChunk:
    return AudioChunk(
        AudioWindow(identifier, start, end, 0, 0),
        Path(f"/private/tmp/{identifier}.flac"),
        1,
        "a" * 64,
    )


def _result(
    chunk: AudioChunk,
    words: tuple[str, ...] = ("clean", "transcript"),
    *,
    confidence: float | None = 0.9,
    duration_s: float = 0.3,
) -> ASRChunkResult:
    if not words:
        return ASRChunkResult(chunk, "local", "model", "en", ())
    parsed_words = tuple(
        Word(index * duration_s, (index + 1) * duration_s, text, confidence, chunk.window.id)
        for index, text in enumerate(words)
    )
    return ASRChunkResult(
        chunk,
        "local",
        "model",
        "en",
        (
            AsrSegment(
                0,
                len(words) * duration_s,
                " ".join(words),
                parsed_words,
                None,
                None,
            ),
        ),
    )


def _evaluate(
    chunks: tuple[AudioChunk, ...], results: tuple[ASRChunkResult, ...], volume: float = -20
):
    return evaluate_asr(
        chunks,
        results,
        source_duration_s=max(chunk.window.end_s for chunk in chunks),
        policy=QualityPolicy(),
        mean_volume_dbfs=lambda _: volume,
    )


def test_clean_result_emits_every_quality_gate() -> None:
    report = _evaluate((_chunk("chunk-0000"),), (_result(_chunk("chunk-0000")),))

    assert report.status == "passed"
    assert {check.code for check in report.checks} == {
        "coverage",
        "timestamps",
        "silence",
        "segment_duration",
        "words_per_second",
        "repetition",
        "unique_token_ratio",
        "compression_ratio",
        "confidence",
    }
    assert not report.unresolved_errors


def test_coverage_and_silence_require_one_result_per_chunk_with_evidence() -> None:
    first = _chunk("chunk-0000")
    second = _chunk("chunk-0001", 10, 20)
    empty = _result(first, ())

    missing = _evaluate((first, second), (empty,), volume=-20)
    assert {issue.code for issue in missing.unresolved_errors} >= {"coverage", "silence"}
    silent = _evaluate((first,), (empty,), volume=-60)
    assert silent.status == "passed"
    backend_silent = ASRChunkResult(
        first,
        "local",
        "model",
        "en",
        (),
        no_speech_probability=0.9,
    )
    assert _evaluate((first,), (backend_silent,), volume=-20).status == "passed"
    duplicate = _evaluate((first,), (_result(first), _result(first)))
    assert any(issue.code == "coverage" for issue in duplicate.unresolved_errors)


def test_quality_detects_length_speed_russian_repetition_entropy_compression_and_confidence() -> (
    None
):
    chunk = _chunk("chunk-0000")
    fast = _result(chunk, tuple("word" for _ in range(100)), duration_s=0.01, confidence=0.01)
    report = _evaluate((chunk,), (fast,))

    assert {issue.code for issue in report.unresolved_errors} >= {
        "words_per_second",
        "repetition",
        "unique_token_ratio",
        "compression_ratio",
        "confidence",
    }


def test_recovery_retries_only_failed_chunks_once_and_rechecks_every_gate() -> None:
    good_chunk = _chunk("chunk-0000")
    bad_chunk = _chunk("chunk-0001", 10, 20)
    initial = (_result(good_chunk), _result(bad_chunk, ()))
    report = _evaluate((good_chunk, bad_chunk), initial, volume=-20)
    calls: list[str] = []

    def materialize(parent: AudioChunk, window: AudioWindow) -> AudioChunk:
        return AudioChunk(window, parent.path, parent.size_bytes, parent.sha256)

    def retry(chunk: AudioChunk, options: RecoveryOptions) -> ASRChunkResult:
        calls.append(chunk.window.id)
        assert options.window_duration_s == 15
        return _result(chunk, ("recovered", "speech"))

    recovered = recover_failed_chunks(
        initial,
        report,
        retry,
        QualityPolicy(),
        planned_chunks=(good_chunk, bad_chunk),
        source_duration_s=20,
        mean_volume_dbfs=lambda _: -20,
        materialize=materialize,
    )

    assert recovered.final_report.status == "passed"
    assert recovered.retried_ids == ("chunk-0001",)
    assert calls == ["chunk-0001-retry-00"]


def test_unresolved_recovery_raises_without_marking_success() -> None:
    chunk = _chunk("chunk-0000")
    initial = (_result(chunk, ()),)
    report = _evaluate((chunk,), initial, volume=-20)

    with pytest.raises(UnresolvedQualityError) as raised:
        recover_failed_chunks(
            initial,
            report,
            lambda child, _: _result(child, ()),
            QualityPolicy(),
            planned_chunks=(chunk,),
            source_duration_s=10,
            mean_volume_dbfs=lambda _: -20,
            materialize=lambda parent, window: AudioChunk(
                window, parent.path, parent.size_bytes, parent.sha256
            ),
        )
    assert raised.value.report.status == "failed"
