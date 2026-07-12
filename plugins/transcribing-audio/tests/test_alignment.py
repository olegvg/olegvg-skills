from __future__ import annotations

import pytest

from audio_transcriber.alignment import align_words, merge_turns, rename_speakers
from audio_transcriber.models import AlignedWord, DiarizationTurn, Word


def _word(start_s: float, end_s: float, text: str) -> Word:
    return Word(start_s, end_s, text, 0.9, "chunk-0000")


def _aligned(start_s: float, end_s: float, text: str, speaker: str = "SPEAKER_00") -> AlignedWord:
    return AlignedWord(_word(start_s, end_s, text), speaker, speaker)


def test_align_words_uses_greatest_overlap_then_start_then_raw_label() -> None:
    words = (
        _word(0.5, 1.5, "first"),
        _word(2.0, 4.0, "second"),
        _word(5.0, 6.0, "third"),
    )
    diarization = (
        DiarizationTurn(0.0, 2.0, "SPEAKER_01"),
        DiarizationTurn(1.0, 4.5, "SPEAKER_00"),
        DiarizationTurn(5.0, 7.0, "SPEAKER_01"),
        DiarizationTurn(5.0, 7.0, "SPEAKER_02"),
    )

    aligned = align_words(words, diarization)

    assert [word.raw_speaker for word in aligned] == [
        "SPEAKER_01",
        "SPEAKER_00",
        "SPEAKER_01",
    ]
    assert [word.speaker for word in aligned] == [
        "SPEAKER_01",
        "SPEAKER_00",
        "SPEAKER_01",
    ]


def test_align_words_handles_overlapping_speakers_and_zero_duration_punctuation() -> None:
    words = (_word(1.0, 2.0, "overlap"), _word(2.5, 2.5, ","))
    diarization = (
        DiarizationTurn(0.0, 4.0, "SPEAKER_00"),
        DiarizationTurn(1.0, 3.0, "SPEAKER_01"),
    )

    aligned = align_words(words, diarization)

    assert [word.raw_speaker for word in aligned] == ["SPEAKER_00", "SPEAKER_00"]


def test_align_words_uses_nearest_fallback_with_deterministic_ties() -> None:
    words = (_word(2.0, 2.0, "?"), _word(8.0, 9.0, "later"))
    diarization = (
        DiarizationTurn(0.0, 1.0, "SPEAKER_01"),
        DiarizationTurn(3.0, 4.0, "SPEAKER_00"),
        DiarizationTurn(3.0, 4.0, "SPEAKER_02"),
        DiarizationTurn(6.0, 7.0, "SPEAKER_03"),
    )

    aligned = align_words(words, diarization)

    assert [word.raw_speaker for word in aligned] == ["SPEAKER_01", "SPEAKER_03"]


def test_align_words_rejects_unsorted_inputs_and_missing_diarization() -> None:
    words = (_word(2.0, 3.0, "late"), _word(1.0, 1.5, "early"))
    diarization = (DiarizationTurn(0.0, 4.0, "SPEAKER_00"),)

    with pytest.raises(ValueError, match="chronological"):
        align_words(words, diarization)
    with pytest.raises(ValueError, match="diarization"):
        align_words((_word(1.0, 2.0, "word"),), ())
    with pytest.raises(ValueError, match="sorted"):
        align_words(
            (_word(1.0, 2.0, "word"),),
            (
                DiarizationTurn(2.0, 3.0, "SPEAKER_01"),
                DiarizationTurn(0.0, 1.0, "SPEAKER_00"),
            ),
        )


def test_rename_speakers_preserves_raw_labels_and_validates_the_mapping() -> None:
    words = (_aligned(0.0, 1.0, "hello"), _aligned(1.0, 2.0, "world", "SPEAKER_01"))

    renamed = rename_speakers(words, {"SPEAKER_00": "Alice"})

    assert [word.raw_speaker for word in renamed] == ["SPEAKER_00", "SPEAKER_01"]
    assert [word.speaker for word in renamed] == ["Alice", "SPEAKER_01"]
    with pytest.raises(ValueError, match="unknown"):
        rename_speakers(words, {"SPEAKER_02": "Carol"})
    with pytest.raises(ValueError, match="empty"):
        rename_speakers(words, {"SPEAKER_00": "  "})
    with pytest.raises(ValueError, match="control"):
        rename_speakers(words, {"SPEAKER_00": "Alice\n"})
    with pytest.raises(ValueError, match="duplicate"):
        rename_speakers(words, {"SPEAKER_00": "Guest", "SPEAKER_01": "Guest"})


def test_merge_turns_splits_on_speaker_or_large_gap_and_joins_punctuation() -> None:
    words = (
        _aligned(0.0, 0.5, "Привет"),
        _aligned(0.5, 0.6, ","),
        _aligned(0.6, 1.0, "мир"),
        _aligned(1.0, 1.1, "!"),
        _aligned(1.2, 1.4, "It's"),
        _aligned(1.4, 1.5, "-"),
        _aligned(1.5, 2.0, "тест"),
        _aligned(4.0, 4.5, "later"),
        _aligned(4.6, 5.0, "other", "SPEAKER_01"),
    )

    turns = merge_turns(words)

    assert [(turn.raw_speaker, turn.start_s, turn.end_s, turn.text) for turn in turns] == [
        ("SPEAKER_00", 0.0, 2.0, "Привет, мир! It's-тест"),
        ("SPEAKER_00", 4.0, 4.5, "later"),
        ("SPEAKER_01", 4.6, 5.0, "other"),
    ]
    assert tuple(word.word.text for word in turns[0].words) == (
        "Привет",
        ",",
        "мир",
        "!",
        "It's",
        "-",
        "тест",
    )
