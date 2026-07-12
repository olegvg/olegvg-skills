from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from audio_transcriber.config import Credentials
from audio_transcriber.diarization import PyannoteDiarizer, validate_diarization
from audio_transcriber.errors import SafeError
from audio_transcriber.models import ComputeDevice, DiarizationTurn, SpeakerCount


@dataclass(frozen=True, slots=True)
class _Segment:
    start: float
    end: float


class _Annotation:
    def __init__(self, turns: tuple[tuple[float, float, str], ...]) -> None:
        self._turns = turns

    def itertracks(self, *, yield_label: bool) -> tuple[tuple[_Segment, str, str], ...]:
        assert yield_label
        return tuple(
            (_Segment(start, end), f"track-{index}", label)
            for index, (start, end, label) in enumerate(self._turns)
        )


class _Pipeline:
    def __init__(self, turns: tuple[tuple[float, float, str], ...]) -> None:
        self._turns = turns
        self.devices: list[str] = []
        self.calls: list[tuple[str, dict[str, int]]] = []

    def to(self, device: object) -> _Pipeline:
        self.devices.append(str(device))
        return self

    def __call__(self, audio_path: str, **kwargs: int) -> SimpleNamespace:
        self.calls.append((audio_path, kwargs))
        return SimpleNamespace(speaker_diarization=_Annotation(self._turns))


def _diarizer(
    pipeline: _Pipeline,
    *,
    device: ComputeDevice = ComputeDevice.CPU,
    token: str | None = "hf-test-token",
) -> tuple[PyannoteDiarizer, list[tuple[str, str, str | None]]]:
    factory_calls: list[tuple[str, str, str | None]] = []

    def factory(model: str, revision: str, received_token: str | None) -> _Pipeline:
        factory_calls.append((model, revision, received_token))
        return pipeline

    return (
        PyannoteDiarizer(
            model_id="pyannote/speaker-diarization-community-1",
            revision="3533c8cf8e369892e6b79ff1bf80f7b0286a54ee",
            compute_device=device,
            credentials=Credentials(_openai_api_key=None, _hf_token=token),
            duration_s=10.0,
            pipeline_factory=factory,
            device_factory=lambda value: value,
        ),
        factory_calls,
    )


@pytest.mark.parametrize(
    ("speakers", "expected_kwargs"),
    [
        (SpeakerCount(exact=3), {"min_speakers": 3, "max_speakers": 3}),
        (SpeakerCount(minimum=2), {"min_speakers": 2}),
        (SpeakerCount(maximum=4), {"max_speakers": 4}),
        (SpeakerCount(minimum=2, maximum=4), {"min_speakers": 2, "max_speakers": 4}),
        (SpeakerCount(), {}),
    ],
)
def test_diarizer_passes_only_requested_speaker_count_arguments(
    tmp_path: Path, speakers: SpeakerCount, expected_kwargs: dict[str, int]
) -> None:
    pipeline = _Pipeline(
        ((0.0, 1.0, "SPEAKER_00"), (1.0, 2.0, "SPEAKER_01"), (2.0, 3.0, "SPEAKER_02"))
    )
    diarizer, _ = _diarizer(pipeline)

    turns = diarizer.diarize(tmp_path / "normalized.wav", speakers)

    assert [turn.raw_speaker for turn in turns] == ["SPEAKER_00", "SPEAKER_01", "SPEAKER_02"]
    assert pipeline.calls == [(str(tmp_path / "normalized.wav"), expected_kwargs)]


@pytest.mark.parametrize("device", [ComputeDevice.MPS, ComputeDevice.CUDA, ComputeDevice.CPU])
def test_diarizer_loads_once_lazily_with_approved_model_revision_and_device(
    tmp_path: Path, device: ComputeDevice
) -> None:
    pipeline = _Pipeline(((0.0, 1.0, "SPEAKER_00"),))
    diarizer, factory_calls = _diarizer(pipeline, device=device)

    assert factory_calls == []
    diarizer.diarize(tmp_path / "normalized.wav", SpeakerCount())
    diarizer.diarize(tmp_path / "normalized.wav", SpeakerCount())

    assert factory_calls == [
        (
            "pyannote/speaker-diarization-community-1",
            "3533c8cf8e369892e6b79ff1bf80f7b0286a54ee",
            "hf-test-token",
        )
    ]
    assert pipeline.devices == [device.value]


def test_validate_diarization_accepts_sorted_overlapping_turns_and_automatic_silence() -> None:
    turns = (
        DiarizationTurn(0.0, 2.0, "SPEAKER_00"),
        DiarizationTurn(1.0, 3.0, "SPEAKER_01"),
    )

    validate_diarization(turns, duration_s=3.0, speakers=SpeakerCount())
    validate_diarization((), duration_s=3.0, speakers=SpeakerCount())


def _unchecked_turn(start_s: float, end_s: float, raw_speaker: str) -> DiarizationTurn:
    turn = object.__new__(DiarizationTurn)
    object.__setattr__(turn, "start_s", start_s)
    object.__setattr__(turn, "end_s", end_s)
    object.__setattr__(turn, "raw_speaker", raw_speaker)
    return turn


@pytest.mark.parametrize(
    "turns",
    [
        (_unchecked_turn(-0.1, 1.0, "SPEAKER_00"),),
        (_unchecked_turn(2.0, 1.0, "SPEAKER_00"),),
        (_unchecked_turn(0.0, 3.1, "SPEAKER_00"),),
        (_unchecked_turn(0.0, 1.0, ""),),
        (_unchecked_turn(1.0, 2.0, "SPEAKER_01"), _unchecked_turn(0.0, 1.0, "SPEAKER_00")),
    ],
)
def test_validate_diarization_rejects_invalid_or_unsorted_turns(
    turns: tuple[DiarizationTurn, ...],
) -> None:
    with pytest.raises(ValueError):
        validate_diarization(turns, duration_s=3.0, speakers=SpeakerCount())


def test_validate_diarization_enforces_exact_and_range_counts_without_relabeling() -> None:
    turns = (
        DiarizationTurn(0.0, 1.0, "SPEAKER_00"),
        DiarizationTurn(1.0, 2.0, "SPEAKER_01"),
        DiarizationTurn(2.0, 3.0, "SPEAKER_02"),
    )

    validate_diarization(turns, duration_s=3.0, speakers=SpeakerCount(exact=3))
    validate_diarization(turns, duration_s=3.0, speakers=SpeakerCount(minimum=3))
    with pytest.raises(ValueError, match=r"requested 2.*observed 3"):
        validate_diarization(turns, duration_s=3.0, speakers=SpeakerCount(exact=2))
    with pytest.raises(ValueError, match="maximum"):
        validate_diarization(turns, duration_s=3.0, speakers=SpeakerCount(maximum=2))
    with pytest.raises(ValueError, match=r"requested 2.*observed 0"):
        validate_diarization((), duration_s=3.0, speakers=SpeakerCount(exact=2))


def test_diarizer_redacts_provider_failure_and_never_serializes_the_hf_token(
    tmp_path: Path,
) -> None:
    token = "hf-super-secret"

    def factory(_: str, __: str, ___: str | None) -> _Pipeline:
        raise RuntimeError(f"provider rejected HF_TOKEN={token}")

    diarizer = PyannoteDiarizer(
        model_id="approved-model",
        revision="approved-revision",
        compute_device=ComputeDevice.CPU,
        credentials=Credentials(_openai_api_key=None, _hf_token=token),
        duration_s=10.0,
        pipeline_factory=factory,
        device_factory=lambda value: value,
    )

    with pytest.raises(SafeError) as raised:
        diarizer.diarize(tmp_path / "normalized.wav", SpeakerCount())

    assert token not in raised.value.render(set())
    assert token not in repr(diarizer)
