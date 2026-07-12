from pathlib import Path

import pytest

from audio_transcriber.errors import SafeError, redact_text
from audio_transcriber.cli import main as cli_main
from audio_transcriber.models import (
    ASRChunkResult,
    ASROptions,
    ASRProvenance,
    AlignedWord,
    AsrSegment,
    AudioChunk,
    AudioMetadata,
    AudioStream,
    AudioWindow,
    ChunkingProvenance,
    ComputeDevice,
    DiarizationProvenance,
    DiarizationTurn,
    InputIdentity,
    Mode,
    OutputPaths,
    QualityCheckResult,
    QualityIssue,
    QualityReport,
    SpeakerCount,
    StageName,
    TranscriptDocument,
    TranscriptProvenance,
    TranscriptSpeaker,
    TranscriptTurn,
    Word,
)


def _audio_chunk() -> AudioChunk:
    return AudioChunk(
        window=AudioWindow(
            id="chunk-0",
            start_s=0.0,
            end_s=10.0,
            overlap_before_s=0.0,
            overlap_after_s=2.0,
        ),
        path=Path("/private/tmp/chunk-0.wav"),
        size_bytes=16,
        sha256="a" * 64,
    )


def _word() -> Word:
    return Word(
        start_s=1.0,
        end_s=1.5,
        text="hello",
        confidence=None,
        source_chunk="chunk-0",
    )


def test_speaker_count_rejects_mixed_exact_and_range() -> None:
    with pytest.raises(ValueError, match="mutually exclusive"):
        SpeakerCount(exact=2, minimum=1, maximum=3)


def test_speaker_count_requires_positive_ordered_values() -> None:
    with pytest.raises(ValueError, match="positive"):
        SpeakerCount(exact=0)
    with pytest.raises(ValueError, match="minimum"):
        SpeakerCount(minimum=3, maximum=2)


def test_speaker_count_maps_exact_and_range_to_pyannote() -> None:
    assert SpeakerCount(exact=2).as_pyannote_kwargs() == {"min_speakers": 2, "max_speakers": 2}
    assert SpeakerCount(minimum=1, maximum=3).as_pyannote_kwargs() == {
        "min_speakers": 1,
        "max_speakers": 3,
    }
    assert SpeakerCount().as_pyannote_kwargs() == {}


def test_word_rejects_inverted_timestamp() -> None:
    with pytest.raises(ValueError, match="start"):
        Word(start_s=2.0, end_s=1.0, text="bad", confidence=None, source_chunk="chunk-0")


def test_safe_error_redacts_known_secrets() -> None:
    error = SafeError(stage=StageName.CONFIGURE, message="failed sk-live-secret")
    assert "sk-live-secret" not in error.render({"sk-live-secret"})
    assert "sk-live-secret" not in repr(error)


def test_redact_text_redacts_known_environment_forms() -> None:
    assert redact_text("OPENAI_API_KEY=sk-live-secret", set()) == "[REDACTED]"
    assert redact_text("HF_TOKEN: hf-secret", set()) == "[REDACTED]"


def test_safe_error_renders_optional_context_without_secrets() -> None:
    error = SafeError(
        stage=StageName.ASR,
        message="failed sk-live-secret",
        start_s=1.0,
        end_s=2.0,
        backend="mlx",
        recovery_hint="retry with HF_TOKEN: hf-secret",
    )

    rendered = error.render({"sk-live-secret"})

    assert "1.000s-2.000s" in rendered
    assert "backend=mlx" in rendered
    assert "hf-secret" not in rendered


def test_cli_main_exposes_help_and_configuration_exit_code(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli_main([]) == 2
    with pytest.raises(SystemExit, match="0"):
        cli_main(["--help"])

    captured = capsys.readouterr()
    assert "Transcribe audio" in captured.out


def test_every_persisted_model_round_trips() -> None:
    chunk = _audio_chunk()
    word = _word()
    segment = AsrSegment(
        start_s=1.0,
        end_s=1.5,
        text="hello",
        words=(word,),
        average_log_probability=-0.1,
        no_speech_probability=0.01,
    )
    aligned_word = AlignedWord(word=word, raw_speaker="SPEAKER_00", speaker="Alice")
    issue = QualityIssue(
        code="coverage",
        severity="warning",
        start_s=0.0,
        end_s=1.0,
        chunk_ids=("chunk-0",),
        detail="low coverage",
    )
    values = (
        (SpeakerCount(exact=3), SpeakerCount),
        (
            AudioStream(index=0, codec_name="pcm_s16le", channels=1, sample_rate_hz=16_000),
            AudioStream,
        ),
        (
            AudioMetadata(
                duration_s=10.0,
                format_name="wav",
                size_bytes=16,
                streams=(
                    AudioStream(index=0, codec_name="pcm_s16le", channels=1, sample_rate_hz=16_000),
                ),
            ),
            AudioMetadata,
        ),
        (chunk.window, AudioWindow),
        (chunk, AudioChunk),
        (
            ASROptions(
                model="large-v3-turbo",
                language="en",
                word_timestamps=True,
                condition_on_previous_text=False,
                temperature=0.0,
                beam_size=5,
            ),
            ASROptions,
        ),
        (word, Word),
        (segment, AsrSegment),
        (
            ASRChunkResult(
                chunk=chunk,
                backend="mlx",
                model="large-v3-turbo",
                language="en",
                segments=(segment,),
            ),
            ASRChunkResult,
        ),
        (DiarizationTurn(start_s=1.0, end_s=1.5, raw_speaker="SPEAKER_00"), DiarizationTurn),
        (aligned_word, AlignedWord),
        (
            TranscriptTurn(
                start_s=1.0,
                end_s=1.5,
                raw_speaker="SPEAKER_00",
                speaker="Alice",
                text="hello",
                words=(aligned_word,),
            ),
            TranscriptTurn,
        ),
        (issue, QualityIssue),
        (
            QualityCheckResult(code="coverage", status="warning", detail="low coverage"),
            QualityCheckResult,
        ),
        (
            QualityReport(
                policy_version="1",
                status="passed",
                checks=(QualityCheckResult(code="coverage", status="passed", detail="ok"),),
                warnings=(issue,),
                unresolved_errors=(),
            ),
            QualityReport,
        ),
        (
            OutputPaths(
                json=Path("/private/tmp/out.json"),
                txt=Path("/private/tmp/out.txt"),
                srt=None,
                vtt=Path("/private/tmp/out.vtt"),
            ),
            OutputPaths,
        ),
    )

    for value, model_type in values:
        assert model_type.from_dict(value.to_dict()) == value


def test_stage_three_document_models_round_trip() -> None:
    word = _word()
    aligned = AlignedWord(word=word, raw_speaker="SPEAKER_00", speaker="Alice")
    turn = TranscriptTurn(1.0, 1.5, "SPEAKER_00", "Alice", "hello", (aligned,))
    identity = InputIdentity(Path("/private/tmp/recording.wav"), 16, 1, "a" * 64)
    chunking = ChunkingProvenance(max_duration_s=600.0, overlap_s=2.0)
    asr = ASRProvenance(Mode.LOCAL, "mlx", "large-v3-turbo", chunking, "en")
    diarization = DiarizationProvenance(
        "pyannote/speaker-diarization-community-1",
        "3533c8cf8e369892e6b79ff1bf80f7b0286a54ee",
        ComputeDevice.MPS,
        SpeakerCount(exact=1),
    )
    provenance = TranscriptProvenance("1", "b" * 64, (StageName.DIARIZE, StageName.ALIGN), ())
    quality = QualityReport(
        policy_version="1",
        status="passed",
        checks=(QualityCheckResult("coverage", "passed", "passed"),),
        warnings=(),
        unresolved_errors=(),
    )
    document = TranscriptDocument(
        1,
        identity,
        10.0,
        "en",
        asr,
        diarization,
        provenance,
        (TranscriptSpeaker("SPEAKER_00", "Alice"),),
        (turn,),
        quality,
    )

    for value, model_type in (
        (identity, InputIdentity),
        (chunking, ChunkingProvenance),
        (asr, ASRProvenance),
        (diarization, DiarizationProvenance),
        (provenance, TranscriptProvenance),
        (TranscriptSpeaker("SPEAKER_00", "Alice"), TranscriptSpeaker),
        (document, TranscriptDocument),
    ):
        assert model_type.from_dict(value.to_dict()) == value


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"start_s": 0.0, "end_s": 1.0, "text": "ok", "confidence": None}, "keys"),
        (
            {
                "start_s": 0.0,
                "end_s": 1.0,
                "text": "ok",
                "confidence": None,
                "source_chunk": "chunk-0",
                "extra": "no",
            },
            "keys",
        ),
        (
            {
                "start_s": float("nan"),
                "end_s": 1.0,
                "text": "ok",
                "confidence": None,
                "source_chunk": "chunk-0",
            },
            "finite",
        ),
    ],
)
def test_word_from_dict_rejects_invalid_persisted_data(
    payload: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        Word.from_dict(payload)


def test_models_are_immutable() -> None:
    word = _word()
    with pytest.raises((AttributeError, TypeError)):
        word.text = "changed"  # type: ignore[misc]


def test_mode_values_are_machine_readable() -> None:
    assert Mode.LOCAL == "local"
