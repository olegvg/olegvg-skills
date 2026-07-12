"""Deterministic ASR quality gates and one bounded, isolated recovery attempt."""

from __future__ import annotations

import re
import zlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .asr import merge_chunk_results
from .constants import DEFAULT_QUALITY_POLICY_VERSION
from .models import (
    ASRChunkResult,
    AsrSegment,
    AudioChunk,
    AudioWindow,
    QualityCheckResult,
    QualityIssue,
    QualityReport,
    StageName,
    Word,
)

if TYPE_CHECKING:
    from .state import RunStateStore

_TOKEN = re.compile(r"\b\w+\b", re.UNICODE)
_BACKEND_SILENCE_THRESHOLD = 0.80


@dataclass(frozen=True, slots=True)
class QualityPolicy:
    version: str = DEFAULT_QUALITY_POLICY_VERSION
    timestamp_epsilon_s: float = 0.05
    silence_mean_volume_dbfs: float = -50.0
    max_segment_duration_s: float = 60.0
    max_words_per_second: float = 8.0
    ngram_sizes: tuple[int, ...] = (3, 4, 5, 6)
    max_consecutive_ngram_repeats: int = 3
    min_unique_token_ratio: float = 0.20
    unique_ratio_min_tokens: int = 20
    max_compression_ratio: float = 2.4
    low_confidence_probability: float = 0.15
    max_low_confidence_fraction: float = 0.50
    min_confidence_word_count: int = 10
    min_confidence_coverage_fraction: float = 0.80
    retry_window_s: float = 15.0
    retry_overlap_s: float = 0.5

    def __post_init__(self) -> None:
        if not self.version:
            raise ValueError("quality policy version must be non-empty")
        positive = (
            self.timestamp_epsilon_s,
            self.max_segment_duration_s,
            self.max_words_per_second,
            self.max_compression_ratio,
            self.retry_window_s,
        )
        if any(value <= 0 for value in positive):
            raise ValueError("quality policy positive thresholds must be greater than zero")
        if self.retry_overlap_s < 0 or self.retry_overlap_s >= self.retry_window_s:
            raise ValueError("quality retry overlap must be smaller than its window")
        if not self.ngram_sizes or any(size < 2 for size in self.ngram_sizes):
            raise ValueError("quality n-gram sizes must be at least two")
        if self.max_consecutive_ngram_repeats < 1 or self.unique_ratio_min_tokens < 1:
            raise ValueError("quality integer thresholds are invalid")
        fractions = (
            self.min_unique_token_ratio,
            self.low_confidence_probability,
            self.max_low_confidence_fraction,
            self.min_confidence_coverage_fraction,
        )
        if any(value < 0 or value > 1 for value in fractions):
            raise ValueError("quality probability thresholds must be between zero and one")


@dataclass(frozen=True, slots=True)
class RecoveryOptions:
    window_duration_s: float
    overlap_s: float
    language: str | None
    temperature: float
    beam_size: int

    def __post_init__(self) -> None:
        if (
            self.window_duration_s <= 0
            or self.overlap_s < 0
            or self.overlap_s >= self.window_duration_s
        ):
            raise ValueError("recovery window is invalid")
        if self.temperature != 0:
            raise ValueError("recovery temperature must be deterministic zero")
        if self.beam_size < 1:
            raise ValueError("recovery beam size must be positive")


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    replacement_results: tuple[ASRChunkResult, ...]
    retried_ids: tuple[str, ...]
    final_report: QualityReport
    unresolved_intervals: tuple[tuple[float, float], ...]


class UnresolvedQualityError(Exception):
    def __init__(self, report: QualityReport) -> None:
        super().__init__("ASR quality remained unresolved after the one permitted recovery pass")
        self.report = report


def _words(result: ASRChunkResult) -> tuple[Word, ...]:
    return tuple(word for segment in result.segments for word in segment.words)


def _tokens(results: Sequence[ASRChunkResult]) -> tuple[str, ...]:
    return tuple(
        token.casefold()
        for result in results
        for word in _words(result)
        for token in _TOKEN.findall(word.text)
    )


def _issue(code: str, chunk: AudioChunk, detail: str) -> QualityIssue:
    return QualityIssue(
        code=code,
        severity="error",
        start_s=chunk.window.start_s,
        end_s=chunk.window.end_s,
        chunk_ids=(chunk.window.id,),
        detail=detail,
    )


def _check(
    checks: list[QualityCheckResult],
    code: str,
    issues: Sequence[QualityIssue],
    *,
    applicable: bool = True,
) -> None:
    if not applicable:
        checks.append(
            QualityCheckResult(code=code, status="not_applicable", detail="not applicable")
        )
    elif issues:
        checks.append(QualityCheckResult(code=code, status="failed", detail=issues[0].detail))
    else:
        checks.append(QualityCheckResult(code=code, status="passed", detail="passed"))


def _has_repeated_ngram(tokens: Sequence[str], policy: QualityPolicy) -> bool:
    for size in policy.ngram_sizes:
        previous: tuple[str, ...] | None = None
        repeats = 0
        for index in range(0, len(tokens) - size + 1):
            ngram = tuple(tokens[index : index + size])
            if ngram == previous:
                repeats += 1
            else:
                previous = ngram
                repeats = 1
            if repeats > policy.max_consecutive_ngram_repeats:
                return True
    return False


def evaluate_asr(
    planned_chunks: Sequence[AudioChunk],
    results: Sequence[ASRChunkResult],
    *,
    source_duration_s: float,
    policy: QualityPolicy,
    mean_volume_dbfs: Callable[[AudioChunk], float],
) -> QualityReport:
    """Evaluate every configured gate; failures retain exact private-run intervals."""
    if source_duration_s <= 0:
        raise ValueError("source duration must be positive")
    planned_by_id = {chunk.window.id: chunk for chunk in planned_chunks}
    if len(planned_by_id) != len(planned_chunks):
        raise ValueError("planned chunk IDs must be unique")
    result_by_id: dict[str, ASRChunkResult] = {}
    duplicate_ids: set[str] = set()
    unexpected: list[ASRChunkResult] = []
    for result in results:
        identifier = result.chunk.window.id
        if identifier not in planned_by_id:
            unexpected.append(result)
        elif identifier in result_by_id:
            duplicate_ids.add(identifier)
        else:
            result_by_id[identifier] = result

    checks: list[QualityCheckResult] = []
    errors: list[QualityIssue] = []
    coverage_errors: list[QualityIssue] = []
    for chunk in planned_chunks:
        identifier = chunk.window.id
        if identifier not in result_by_id:
            coverage_errors.append(_issue("coverage", chunk, "planned chunk has no ASR result"))
        if identifier in duplicate_ids:
            coverage_errors.append(
                _issue("coverage", chunk, "planned chunk has duplicate ASR results")
            )
    for result in unexpected:
        coverage_errors.append(
            QualityIssue(
                code="coverage",
                severity="error",
                start_s=result.chunk.window.start_s,
                end_s=result.chunk.window.end_s,
                chunk_ids=(result.chunk.window.id,),
                detail="ASR result does not match a planned chunk",
            )
        )
    _check(checks, "coverage", coverage_errors)
    errors.extend(coverage_errors)

    timestamp_errors: list[QualityIssue] = []
    for identifier, result in result_by_id.items():
        duration = planned_by_id[identifier].window.end_s - planned_by_id[identifier].window.start_s
        previous_start = -policy.timestamp_epsilon_s
        previous_end = -policy.timestamp_epsilon_s
        for word in _words(result):
            if (
                word.start_s < -policy.timestamp_epsilon_s
                or word.end_s > duration + policy.timestamp_epsilon_s
                or word.start_s < previous_start
                or word.end_s < previous_end
            ):
                timestamp_errors.append(
                    _issue(
                        "timestamps",
                        planned_by_id[identifier],
                        "word timestamps are out of bounds or unordered",
                    )
                )
                break
            previous_start = word.start_s
            previous_end = word.end_s
    _check(checks, "timestamps", timestamp_errors)
    errors.extend(timestamp_errors)

    silence_errors: list[QualityIssue] = []
    for identifier, result in result_by_id.items():
        if result.segments:
            continue
        backend_silence = (
            result.no_speech_probability is not None
            and result.no_speech_probability >= _BACKEND_SILENCE_THRESHOLD
        )
        if (
            not backend_silence
            and mean_volume_dbfs(planned_by_id[identifier]) > policy.silence_mean_volume_dbfs
        ):
            silence_errors.append(
                _issue(
                    "silence",
                    planned_by_id[identifier],
                    "empty ASR result is not supported by silence evidence",
                )
            )
    _check(checks, "silence", silence_errors)
    errors.extend(silence_errors)

    duration_errors: list[QualityIssue] = []
    for identifier, result in result_by_id.items():
        if any(
            segment.end_s - segment.start_s > policy.max_segment_duration_s
            for segment in result.segments
        ):
            duration_errors.append(
                _issue(
                    "segment_duration",
                    planned_by_id[identifier],
                    "ASR segment exceeds maximum duration",
                )
            )
    _check(checks, "segment_duration", duration_errors)
    errors.extend(duration_errors)

    speed_errors: list[QualityIssue] = []
    for identifier, result in result_by_id.items():
        duration = planned_by_id[identifier].window.end_s - planned_by_id[identifier].window.start_s
        if duration > 0 and len(_words(result)) / duration > policy.max_words_per_second:
            speed_errors.append(
                _issue(
                    "words_per_second",
                    planned_by_id[identifier],
                    "ASR word rate exceeds quality threshold",
                )
            )
    _check(checks, "words_per_second", speed_errors)
    errors.extend(speed_errors)

    result_values = tuple(result_by_id.values())
    tokens = _tokens(result_values)
    text = " ".join(word.text for result in result_values for word in _words(result))
    all_chunks = tuple(result.chunk for result in result_values) or tuple(planned_chunks)
    text_chunk = all_chunks[0]

    repetition_errors: list[QualityIssue] = []
    if tokens and _has_repeated_ngram(tokens, policy):
        repetition_errors.append(
            _issue("repetition", text_chunk, "repeated token n-gram indicates an ASR loop")
        )
    _check(checks, "repetition", repetition_errors, applicable=bool(tokens))
    errors.extend(repetition_errors)

    entropy_errors: list[QualityIssue] = []
    entropy_applicable = len(tokens) >= policy.unique_ratio_min_tokens
    if entropy_applicable and len(set(tokens)) / len(tokens) < policy.min_unique_token_ratio:
        entropy_errors.append(
            _issue("unique_token_ratio", text_chunk, "transcript token diversity is too low")
        )
    _check(checks, "unique_token_ratio", entropy_errors, applicable=entropy_applicable)
    errors.extend(entropy_errors)

    compression_errors: list[QualityIssue] = []
    compression_applicable = bool(text)
    if compression_applicable:
        encoded = text.encode("utf-8")
        compressed = zlib.compress(encoded)
        ratio = len(encoded) / len(compressed) if compressed else 0.0
        if ratio > policy.max_compression_ratio:
            compression_errors.append(
                _issue(
                    "compression_ratio",
                    text_chunk,
                    "transcript compression ratio indicates repetition",
                )
            )
    _check(checks, "compression_ratio", compression_errors, applicable=compression_applicable)
    errors.extend(compression_errors)

    all_words = tuple(word for result in result_values for word in _words(result))
    confidence_words = tuple(word for word in all_words if word.confidence is not None)
    confidence_errors: list[QualityIssue] = []
    confidence_applicable = (
        len(all_words) >= policy.min_confidence_word_count
        and len(confidence_words) / len(all_words) >= policy.min_confidence_coverage_fraction
    )
    if confidence_applicable:
        low_fraction = sum(
            1
            for word in confidence_words
            if word.confidence is not None and word.confidence < policy.low_confidence_probability
        ) / len(confidence_words)
        if low_fraction > policy.max_low_confidence_fraction:
            confidence_errors.append(
                _issue("confidence", text_chunk, "too many timestamped words have low confidence")
            )
    _check(checks, "confidence", confidence_errors, applicable=confidence_applicable)
    errors.extend(confidence_errors)

    return QualityReport(
        policy_version=policy.version,
        status="failed" if errors else "passed",
        checks=tuple(checks),
        warnings=(),
        unresolved_errors=tuple(errors),
    )


def _recovery_windows(chunk: AudioChunk, policy: QualityPolicy) -> tuple[AudioWindow, ...]:
    windows: list[AudioWindow] = []
    start = chunk.window.start_s
    index = 0
    while start < chunk.window.end_s:
        end = min(start + policy.retry_window_s, chunk.window.end_s)
        windows.append(
            AudioWindow(
                id=f"{chunk.window.id}-retry-{index:02d}",
                start_s=start,
                end_s=end,
                overlap_before_s=0.0 if index == 0 else policy.retry_overlap_s,
                overlap_after_s=0.0 if end >= chunk.window.end_s else policy.retry_overlap_s,
            )
        )
        if end >= chunk.window.end_s:
            break
        start = end - policy.retry_overlap_s
        index += 1
    return tuple(windows)


def _combine_recovery_results(
    parent: AudioChunk, children: Sequence[ASRChunkResult]
) -> ASRChunkResult:
    if not children:
        raise ValueError("recovery requires at least one retry result")
    languages = {result.language for result in children if result.language is not None}
    if len(languages) > 1:
        raise ValueError("recovery chunks detected incompatible languages")
    words = merge_chunk_results(children)
    relative_words = tuple(
        Word(
            start_s=word.start_s - parent.window.start_s,
            end_s=word.end_s - parent.window.start_s,
            text=word.text,
            confidence=word.confidence,
            source_chunk=parent.window.id,
        )
        for word in words
    )
    segments = tuple(
        AsrSegment(
            start_s=word.start_s,
            end_s=word.end_s,
            text=word.text,
            words=(word,),
            average_log_probability=None,
            no_speech_probability=None,
        )
        for word in relative_words
    )
    first = children[0]
    no_speech_probabilities = tuple(
        result.no_speech_probability
        for result in children
        if result.no_speech_probability is not None
    )
    return ASRChunkResult(
        chunk=parent,
        backend=first.backend,
        model=first.model,
        language=next(iter(languages), None),
        segments=segments,
        no_speech_probability=max(no_speech_probabilities, default=None),
    )


def recover_failed_chunks(
    results: Sequence[ASRChunkResult],
    report: QualityReport,
    retry: Callable[[AudioChunk, RecoveryOptions], ASRChunkResult],
    policy: QualityPolicy,
    *,
    planned_chunks: Sequence[AudioChunk],
    source_duration_s: float,
    mean_volume_dbfs: Callable[[AudioChunk], float],
    materialize: Callable[[AudioChunk, AudioWindow], AudioChunk],
    state_store: RunStateStore | None = None,
) -> RecoveryResult:
    """Retry only failed intervals once, then require a complete fresh quality pass."""
    by_id = {chunk.window.id: chunk for chunk in planned_chunks}
    failed_ids = {
        chunk_id
        for issue in report.unresolved_errors
        for chunk_id in issue.chunk_ids
        if chunk_id in by_id
    }
    replacements: list[ASRChunkResult] = []
    retried_ids: list[str] = []
    for parent in planned_chunks:
        if parent.window.id not in failed_ids:
            continue
        child_results: list[ASRChunkResult] = []
        language = next(
            (result.language for result in results if result.chunk.window.id == parent.window.id),
            None,
        )
        options = RecoveryOptions(
            window_duration_s=policy.retry_window_s,
            overlap_s=policy.retry_overlap_s,
            language=language,
            temperature=0.0,
            beam_size=5,
        )
        for window in _recovery_windows(parent, policy):
            child = materialize(parent, window)
            if child.window != window:
                raise ValueError("recovery materializer returned an unexpected chunk window")
            retried = retry(child, options)
            if retried.chunk.window.id != window.id:
                raise ValueError("recovery retry returned an unexpected chunk result")
            child_results.append(retried)
        replacements.append(_combine_recovery_results(parent, child_results))
        retried_ids.append(parent.window.id)

    replacement_by_id = {result.chunk.window.id: result for result in replacements}
    final_results = tuple(
        replacement_by_id.get(chunk.window.id)
        or next(
            (
                result
                for result in results
                if result.chunk.window.id == chunk.window.id and chunk.window.id not in failed_ids
            ),
            None,
        )
        for chunk in planned_chunks
    )
    completed_results = tuple(result for result in final_results if result is not None)
    final_report = evaluate_asr(
        planned_chunks,
        completed_results,
        source_duration_s=source_duration_s,
        policy=policy,
        mean_volume_dbfs=mean_volume_dbfs,
    )
    unresolved = tuple((issue.start_s, issue.end_s) for issue in final_report.unresolved_errors)
    recovery = RecoveryResult(
        replacement_results=tuple(replacements),
        retried_ids=tuple(retried_ids),
        final_report=final_report,
        unresolved_intervals=unresolved,
    )
    if final_report.status == "failed":
        if state_store is not None:
            state_store.record_failure(
                stage=StageName.QUALITY,
                report={
                    "policy_version": policy.version,
                    "unresolved_intervals": [list(interval) for interval in unresolved],
                },
            )
        raise UnresolvedQualityError(final_report)
    return recovery
