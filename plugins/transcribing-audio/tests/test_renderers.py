from __future__ import annotations

import json
import stat
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from audio_transcriber.models import (
    ASRProvenance,
    AlignedWord,
    ChunkingProvenance,
    ComputeDevice,
    DiarizationProvenance,
    DiarizationTurn,
    InputIdentity,
    Mode,
    QualityCheckResult,
    QualityIssue,
    QualityReport,
    SpeakerCount,
    StageName,
    TranscriptProvenance,
    TranscriptDocument,
    TranscriptTurn,
    Word,
)
from audio_transcriber.renderers import (
    build_transcript_document,
    default_output_paths,
    load_json,
    render_json,
    render_srt,
    render_txt,
    render_vtt,
    validate_transcript,
)


def _document() -> TranscriptDocument:
    word = Word(90_003.2, 90_006.1, "Пример текста.", None, "chunk-0000")
    aligned = AlignedWord(word, "SPEAKER_00", "Алиса")
    turn = TranscriptTurn(90_003.2, 90_006.1, "SPEAKER_00", "Алиса", "Пример текста.", (aligned,))
    return build_transcript_document(
        input_identity=InputIdentity(
            canonical_path=Path("/private/tmp/meeting.wav"),
            size_bytes=123,
            mtime_ns=456,
            sample_digest="a" * 64,
        ),
        duration_s=90_010.0,
        language="ru",
        asr=ASRProvenance(
            mode=Mode.LOCAL,
            backend="mlx",
            model="large-v3-turbo",
            chunking=ChunkingProvenance(max_duration_s=600.0, overlap_s=2.0),
            detected_language="ru",
        ),
        diarization=DiarizationProvenance(
            model="pyannote/speaker-diarization-community-1",
            revision="3533c8cf8e369892e6b79ff1bf80f7b0286a54ee",
            compute_device=ComputeDevice.MPS,
            speaker_count=SpeakerCount(exact=1),
        ),
        provenance=TranscriptProvenance(
            runtime_version="1",
            run_fingerprint="b" * 64,
            completed_stages=(StageName.ASR, StageName.QUALITY, StageName.DIARIZE, StageName.ALIGN),
            retries=(),
        ),
        diarization_turns=(DiarizationTurn(0.0, 90_010.0, "SPEAKER_00"),),
        turns=(turn,),
        quality=QualityReport(
            policy_version="1",
            status="passed",
            checks=(QualityCheckResult("coverage", "passed", "passed"),),
            warnings=(),
            unresolved_errors=(),
        ),
        speaker_names={"SPEAKER_00": "Алиса"},
    )


def test_canonical_document_has_exact_schema_and_json_round_trips(tmp_path: Path) -> None:
    document = _document()
    path = render_json(document, tmp_path / "stage.json")

    payload = json.loads(path.read_text(encoding="utf-8"))

    assert set(payload) == {
        "schema_version",
        "input",
        "language",
        "asr",
        "diarization",
        "provenance",
        "speakers",
        "turns",
        "quality",
    }
    assert payload["input"] == {
        "canonical_path": "/private/tmp/meeting.wav",
        "size": 123,
        "mtime_ns": 456,
        "sample_digest": "a" * 64,
        "duration_s": 90_010.0,
    }
    assert load_json(path) == document
    assert path.read_bytes().endswith(b"\n")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_document_validation_rejects_schema_and_content_contract_violations() -> None:
    document = _document()
    payload = document.to_dict()
    input_payload = cast(dict[str, object], payload["input"])
    turns_payload = cast(list[object], payload["turns"])
    turn_payload = cast(dict[str, object], turns_payload[0])
    words_payload = cast(list[object], turn_payload["words"])
    aligned_word_payload = cast(dict[str, object], words_payload[0])

    invalid_payloads: tuple[dict[str, object], ...] = (
        {key: value for key, value in payload.items() if key != "quality"},
        payload | {"extra": True},
        payload | {"input": input_payload | {"duration_s": float("nan")}},
        payload | {"turns": [turn_payload | {"text": "", "words": words_payload}]},
        payload | {"turns": [turn_payload | {"raw_speaker": "UNKNOWN", "speaker": "UNKNOWN"}]},
        payload
        | {
            "turns": [
                turn_payload
                | {
                    "words": [
                        {key: value for key, value in aligned_word_payload.items() if key != "word"}
                    ]
                }
            ]
        },
    )
    for invalid in invalid_payloads:
        with pytest.raises(ValueError):
            validate_transcript(TranscriptDocument.from_dict(invalid))

    with pytest.raises(ValueError, match="exact"):
        validate_transcript(
            replace(
                document,
                diarization=replace(document.diarization, speaker_count=SpeakerCount(exact=2)),
            )
        )
    overlapping_word = Word(90_005.0, 90_007.0, "overlap", None, "chunk-0001")
    overlapping_turn = TranscriptTurn(
        90_005.0,
        90_007.0,
        "SPEAKER_00",
        "Алиса",
        "overlap",
        (AlignedWord(overlapping_word, "SPEAKER_00", "Алиса"),),
    )
    with pytest.raises(ValueError, match="overlap"):
        validate_transcript(replace(document, turns=document.turns + (overlapping_turn,)))
    out_of_bounds_word = Word(90_011.0, 90_012.0, "late", None, "chunk-0001")
    out_of_bounds_turn = TranscriptTurn(
        90_011.0,
        90_012.0,
        "SPEAKER_00",
        "Алиса",
        "late",
        (AlignedWord(out_of_bounds_word, "SPEAKER_00", "Алиса"),),
    )
    with pytest.raises(ValueError, match="outside"):
        validate_transcript(replace(document, turns=(out_of_bounds_turn,)))
    with pytest.raises(ValueError, match="quality"):
        validate_transcript(
            replace(
                document,
                quality=QualityReport(
                    policy_version="1",
                    status="failed",
                    checks=(),
                    warnings=(),
                    unresolved_errors=(
                        QualityIssue("coverage", "error", 0.0, 1.0, ("chunk-0",), "failed"),
                    ),
                ),
            )
        )


def test_build_document_preserves_diarized_silent_speakers_and_rejects_collapsed_names() -> None:
    document = _document()
    silent = DiarizationTurn(10.0, 11.0, "SPEAKER_01")

    result = build_transcript_document(
        input_identity=document.input_identity,
        duration_s=document.duration_s,
        language=document.language,
        asr=document.asr,
        diarization=replace(document.diarization, speaker_count=SpeakerCount(exact=2)),
        provenance=document.provenance,
        diarization_turns=(DiarizationTurn(0.0, 90_010.0, "SPEAKER_00"), silent),
        turns=document.turns,
        quality=document.quality,
        speaker_names={"SPEAKER_00": "Алиса", "SPEAKER_01": "Борис"},
    )

    assert [(speaker.raw_label, speaker.display_name) for speaker in result.speakers] == [
        ("SPEAKER_00", "Алиса"),
        ("SPEAKER_01", "Борис"),
    ]
    with pytest.raises(ValueError, match="duplicate"):
        build_transcript_document(
            input_identity=document.input_identity,
            duration_s=document.duration_s,
            language=document.language,
            asr=document.asr,
            diarization=replace(document.diarization, speaker_count=SpeakerCount(exact=2)),
            provenance=document.provenance,
            diarization_turns=(DiarizationTurn(0.0, 90_010.0, "SPEAKER_00"), silent),
            turns=document.turns,
            quality=document.quality,
            speaker_names={"SPEAKER_00": "Guest", "SPEAKER_01": "Guest"},
        )


def test_renderers_derive_all_human_formats_from_the_validated_document(tmp_path: Path) -> None:
    document = _document()
    json_path = render_json(document, tmp_path / "canonical.json")
    loaded = load_json(json_path)
    txt_path = tmp_path / "existing.txt"
    txt_path.write_text("stale", encoding="utf-8")
    txt_path = render_txt(loaded, txt_path)
    srt_path = render_srt(loaded, tmp_path / "output.srt")
    vtt_path = render_vtt(loaded, tmp_path / "output.vtt")

    assert txt_path.read_text(encoding="utf-8") == "[25:00:03–25:00:07] Алиса: Пример текста.\n"
    assert srt_path.read_text(encoding="utf-8") == (
        "1\n25:00:03,200 --> 25:00:06,100\nАлиса: Пример текста.\n"
    )
    assert vtt_path.read_text(encoding="utf-8") == (
        "WEBVTT\n\n25:00:03.200 --> 25:00:06.100\nАлиса: Пример текста.\n"
    )
    for path in (txt_path, srt_path, vtt_path):
        assert path.read_text(encoding="utf-8")
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_default_output_paths_and_renderers_reject_empty_staging_paths(tmp_path: Path) -> None:
    paths = default_output_paths(Path("meeting.final.wav"), tmp_path, srt=True, vtt=False)

    assert paths.json == tmp_path / "meeting.final.transcript.json"
    assert paths.txt == tmp_path / "meeting.final.transcript.txt"
    assert paths.srt == tmp_path / "meeting.final.transcript.srt"
    assert paths.vtt is None
    with pytest.raises(ValueError, match="filename"):
        render_txt(_document(), Path())
    with pytest.raises(ValueError, match="input path"):
        default_output_paths(Path(), tmp_path, srt=False, vtt=False)
