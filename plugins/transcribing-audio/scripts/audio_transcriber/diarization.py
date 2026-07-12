"""Local pyannote speaker diarization with secret-safe validation."""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Literal, Protocol, cast

import torch
from pyannote.audio import Pipeline

from .config import Credentials
from .errors import SafeError, redact_text
from .models import ComputeDevice, DiarizationTurn, SpeakerCount, StageName


class _PyannotePipeline(Protocol):
    def to(self, device: object) -> object: ...

    def __call__(self, audio_path: str, **kwargs: int) -> object: ...


class _PyannoteSegment(Protocol):
    start: float
    end: float


class _PyannoteAnnotation(Protocol):
    def itertracks(
        self, *, yield_label: Literal[True]
    ) -> Iterable[tuple[_PyannoteSegment, object, str]]: ...


PipelineFactory = Callable[[str, str, str | None], _PyannotePipeline]
DeviceFactory = Callable[[str], object]


def _load_pipeline(model_id: str, revision: str, token: str | None) -> _PyannotePipeline:
    pipeline = Pipeline.from_pretrained(  # type: ignore[reportUnknownMemberType]
        model_id, revision=revision, token=token
    )
    if pipeline is None:
        raise RuntimeError("pyannote did not return a diarization pipeline")
    return cast(_PyannotePipeline, pipeline)


def _validate_duration(duration_s: float) -> None:
    if not math.isfinite(duration_s) or duration_s < 0:
        raise ValueError("diarization duration must be a finite non-negative number")


def _validate_label(label: str) -> None:
    if not label.strip():
        raise ValueError("diarization raw speaker labels must not be empty")
    if any(character.isspace() and character not in {" "} for character in label):
        raise ValueError("diarization raw speaker labels must not contain control characters")


def validate_diarization(
    turns: Sequence[DiarizationTurn], *, duration_s: float, speakers: SpeakerCount
) -> None:
    """Validate raw local labels without conflating them with identities."""
    _validate_duration(duration_s)
    previous_key: tuple[float, float, str] | None = None
    labels: set[str] = set()
    for turn in turns:
        if not math.isfinite(turn.start_s) or not math.isfinite(turn.end_s):
            raise ValueError("diarization timestamps must be finite")
        if turn.start_s < 0 or turn.end_s < turn.start_s or turn.end_s > duration_s:
            raise ValueError("diarization turn lies outside the normalized audio duration")
        _validate_label(turn.raw_speaker)
        key = (turn.start_s, turn.end_s, turn.raw_speaker)
        if previous_key is not None and key < previous_key:
            raise ValueError("diarization turns must be sorted by start, end, and raw label")
        previous_key = key
        labels.add(turn.raw_speaker)

    observed = len(labels)
    if speakers.exact is not None and observed != speakers.exact:
        raise ValueError(
            "diarization exact speaker count mismatch: "
            f"requested {speakers.exact}, observed {observed}; "
            "check the requested count or retry with automatic speaker inference"
        )
    if speakers.minimum is not None and observed < speakers.minimum:
        raise ValueError(
            "diarization minimum speaker count mismatch: "
            f"minimum {speakers.minimum}, observed {observed}"
        )
    if speakers.maximum is not None and observed > speakers.maximum:
        raise ValueError(
            "diarization maximum speaker count mismatch: "
            f"maximum {speakers.maximum}, observed {observed}"
        )


class PyannoteDiarizer:
    """Lazy local pyannote adapter for one normalized recording duration."""

    def __init__(
        self,
        *,
        model_id: str,
        revision: str,
        compute_device: ComputeDevice,
        credentials: Credentials,
        duration_s: float,
        pipeline_factory: PipelineFactory = _load_pipeline,
        device_factory: DeviceFactory = torch.device,
    ) -> None:
        if not model_id or not revision:
            raise ValueError("diarization model ID and revision must be non-empty")
        _validate_duration(duration_s)
        self._model_id = model_id
        self._revision = revision
        self._compute_device = compute_device
        self._credentials = credentials
        self._duration_s = duration_s
        self._pipeline_factory = pipeline_factory
        self._device_factory = device_factory
        self._pipeline: _PyannotePipeline | None = None

    def _get_pipeline(self) -> _PyannotePipeline:
        if self._pipeline is None:
            try:
                pipeline = self._pipeline_factory(
                    self._model_id, self._revision, self._credentials.hf_token
                )
                pipeline.to(self._device_factory(self._compute_device.value))
            except Exception as exc:
                raise SafeError(
                    stage=StageName.DIARIZE,
                    message=redact_text(str(exc), self._secret_values()),
                    backend="pyannote",
                    recovery_hint=(
                        "Confirm local pyannote dependencies and approved Hugging Face model access."
                    ),
                ) from None
            self._pipeline = pipeline
        return self._pipeline

    def _secret_values(self) -> set[str]:
        return {value for value in (self._credentials.hf_token,) if value}

    def health_check(self) -> None:
        """Load the gated local pipeline before any ASR upload can start."""
        self._get_pipeline()

    def diarize(self, audio_path: Path, speakers: SpeakerCount) -> tuple[DiarizationTurn, ...]:
        """Run local pyannote and return sorted raw-label intervals."""
        try:
            output = self._get_pipeline()(str(audio_path), **speakers.as_pyannote_kwargs())
            annotation = cast(_PyannoteAnnotation, getattr(output, "speaker_diarization"))
            turns = tuple(
                sorted(
                    (
                        DiarizationTurn(
                            start_s=float(segment.start),
                            end_s=float(segment.end),
                            raw_speaker=str(raw_label),
                        )
                        for segment, _, raw_label in annotation.itertracks(yield_label=True)
                    ),
                    key=lambda turn: (turn.start_s, turn.end_s, turn.raw_speaker),
                )
            )
            validate_diarization(turns, duration_s=self._duration_s, speakers=speakers)
            return turns
        except SafeError:
            raise
        except Exception as exc:
            raise SafeError(
                stage=StageName.DIARIZE,
                message=redact_text(str(exc), self._secret_values()),
                backend="pyannote",
                recovery_hint="Check local diarization output and requested speaker-count constraints.",
            ) from None
