"""Pure deterministic assignment of ASR words to raw diarization labels."""

from __future__ import annotations

import math
import unicodedata
from collections.abc import Mapping, Sequence

from .models import AlignedWord, DiarizationTurn, TranscriptTurn, Word

_CLOSING_PUNCTUATION = frozenset(".,!?;:…)]}»")
_OPENING_PUNCTUATION = frozenset("([{«")
_CONNECTING_PUNCTUATION = frozenset("'’‐‑-–—")


def _validate_chronological_words(words: Sequence[Word]) -> None:
    previous_start = -1.0
    previous_end = -1.0
    for word in words:
        if word.start_s < previous_start or word.end_s < previous_end:
            raise ValueError("ASR words must be chronological")
        previous_start = word.start_s
        previous_end = word.end_s


def _validate_sorted_diarization(diarization: Sequence[DiarizationTurn]) -> None:
    previous_key: tuple[float, float, str] | None = None
    for turn in diarization:
        key = (turn.start_s, turn.end_s, turn.raw_speaker)
        if previous_key is not None and key < previous_key:
            raise ValueError("diarization turns must be sorted by start, end, and raw label")
        previous_key = key


def _overlap_duration(word: Word, turn: DiarizationTurn) -> float:
    return max(0.0, min(word.end_s, turn.end_s) - max(word.start_s, turn.start_s))


def _interval_distance(word: Word, turn: DiarizationTurn) -> float:
    return max(turn.start_s - word.end_s, word.start_s - turn.end_s, 0.0)


def _speaker_for_word(word: Word, diarization: Sequence[DiarizationTurn]) -> str:
    overlaps = tuple(
        (turn, _overlap_duration(word, turn))
        for turn in diarization
        if _overlap_duration(word, turn) > 0
    )
    if overlaps:
        return min(
            overlaps,
            key=lambda candidate: (
                -candidate[1],
                candidate[0].start_s,
                candidate[0].raw_speaker,
            ),
        )[0].raw_speaker
    return min(
        diarization,
        key=lambda turn: (_interval_distance(word, turn), turn.start_s, turn.raw_speaker),
    ).raw_speaker


def align_words(
    words: Sequence[Word], diarization: Sequence[DiarizationTurn]
) -> tuple[AlignedWord, ...]:
    """Attach a non-identity raw/display speaker label to every ASR word."""
    _validate_chronological_words(words)
    _validate_sorted_diarization(diarization)
    if words and not diarization:
        raise ValueError("diarization is required when ASR contains words")
    return tuple(
        AlignedWord(word=word, raw_speaker=speaker, speaker=speaker)
        for word in words
        for speaker in (_speaker_for_word(word, diarization),)
    )


def _validate_display_name(name: object) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("speaker display names must not be empty")
    if any(unicodedata.category(character).startswith("C") for character in name):
        raise ValueError("speaker display names must not contain control characters")
    return name


def rename_speakers(
    words: Sequence[AlignedWord], names: Mapping[str, str]
) -> tuple[AlignedWord, ...]:
    """Apply a validated display-only mapping without changing raw labels."""
    raw_labels = {word.raw_speaker for word in words}
    unknown = set(names).difference(raw_labels)
    if unknown:
        raise ValueError("speaker name mapping contains an unknown raw label")
    display_by_raw = {
        raw_label: _validate_display_name(names.get(raw_label, raw_label))
        for raw_label in raw_labels
    }
    if len(set(display_by_raw.values())) != len(display_by_raw):
        raise ValueError("speaker name mapping has duplicate display names")
    return tuple(
        AlignedWord(
            word=aligned.word,
            raw_speaker=aligned.raw_speaker,
            speaker=display_by_raw[aligned.raw_speaker],
        )
        for aligned in words
    )


def _validate_chronological_aligned_words(words: Sequence[AlignedWord]) -> None:
    _validate_chronological_words(tuple(word.word for word in words))


def join_word_text(words: Sequence[AlignedWord]) -> str:
    """Render tokenized ASR text with a small language-neutral punctuation policy."""
    result = ""
    previous = ""
    for aligned in words:
        current = aligned.word.text.strip()
        if not current:
            raise ValueError("aligned word text must not be empty")
        if result and not (
            current[0] in _CLOSING_PUNCTUATION | _CONNECTING_PUNCTUATION
            or previous[-1] in _OPENING_PUNCTUATION | _CONNECTING_PUNCTUATION
        ):
            result += " "
        result += current
        previous = current
    return result


def merge_turns(
    words: Sequence[AlignedWord], *, max_same_speaker_gap_s: float = 1.5
) -> tuple[TranscriptTurn, ...]:
    """Merge neighboring same-speaker words while retaining each immutable word."""
    if not math.isfinite(max_same_speaker_gap_s) or max_same_speaker_gap_s < 0:
        raise ValueError("maximum same-speaker gap must be finite and non-negative")
    _validate_chronological_aligned_words(words)
    grouped: list[list[AlignedWord]] = []
    for word in words:
        if not grouped:
            grouped.append([word])
            continue
        previous_group = grouped[-1]
        previous = previous_group[-1]
        gap_s = word.word.start_s - previous.word.end_s
        if (
            word.raw_speaker == previous.raw_speaker
            and word.speaker == previous.speaker
            and gap_s <= max_same_speaker_gap_s
        ):
            previous_group.append(word)
        else:
            grouped.append([word])
    return tuple(
        TranscriptTurn(
            start_s=group[0].word.start_s,
            end_s=group[-1].word.end_s,
            raw_speaker=group[0].raw_speaker,
            speaker=group[0].speaker,
            text=join_word_text(group),
            words=tuple(group),
        )
        for group in grouped
    )
