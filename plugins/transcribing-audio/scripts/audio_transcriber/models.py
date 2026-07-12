"""Immutable, validated values exchanged by transcription runtime stages."""

from __future__ import annotations

import math
import string
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self, cast

from .constants import OUTPUT_SCHEMA_VERSION


class Mode(StrEnum):
    LOCAL = "local"
    OPENAI = "openai"


class BackendFamily(StrEnum):
    MLX = "mlx"
    CUDA = "cuda"
    CPU = "cpu"


class ComputeDevice(StrEnum):
    MPS = "mps"
    CUDA = "cuda"
    CPU = "cpu"


class RuntimeComponent(StrEnum):
    ASR_MLX = "asr:mlx"
    ASR_CUDA = "asr:cuda"
    ASR_CPU = "asr:cpu"
    DIARIZATION_MPS = "diarization:mps"
    DIARIZATION_CUDA = "diarization:cuda"
    DIARIZATION_CPU = "diarization:cpu"


class StageName(StrEnum):
    CONFIGURE = "configure"
    INSPECT = "inspect"
    ASR = "asr"
    QUALITY = "quality"
    DIARIZE = "diarize"
    ALIGN = "align"
    RENDER = "render"


Payload = Mapping[str, object]


def _expect_keys(payload: Payload, expected: set[str]) -> None:
    if set(payload) != expected:
        raise ValueError("payload keys do not match the schema")


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _integer(value: object, field: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{field} must be an integer greater than or equal to {minimum}")
    return value


def _optional_integer(value: object, field: str, *, minimum: int = 1) -> int | None:
    if value is None:
        return None
    return _integer(value, field, minimum=minimum)


def _number(value: object, field: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    if result < minimum:
        raise ValueError(f"{field} must be greater than or equal to {minimum}")
    return result


def _optional_number(value: object, field: str) -> float | None:
    if value is None:
        return None
    return _number(value, field, minimum=-math.inf)


def _timestamp_pair(start_s: float, end_s: float) -> None:
    if end_s < start_s:
        raise ValueError("end timestamp must not precede start timestamp")


def _path(value: object, field: str) -> Path:
    return Path(_string(value, field))


def _optional_path(value: object, field: str) -> Path | None:
    if value is None:
        return None
    return _path(value, field)


def _list(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    return cast(list[object], value)


def _mapping(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    raw_value = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in raw_value):
        raise ValueError(f"{field} must be an object")
    return cast(dict[str, object], value)


@dataclass(frozen=True, slots=True)
class SpeakerCount:
    exact: int | None = None
    minimum: int | None = None
    maximum: int | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("exact", self.exact),
            ("minimum", self.minimum),
            ("maximum", self.maximum),
        ):
            if value is not None and (isinstance(value, bool) or value <= 0):
                raise ValueError(f"{name} must be a positive integer")
        if self.exact is not None and (self.minimum is not None or self.maximum is not None):
            raise ValueError("exact and range speaker counts are mutually exclusive")
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("minimum cannot exceed maximum")

    def as_pyannote_kwargs(self) -> dict[str, int]:
        if self.exact is not None:
            return {"min_speakers": self.exact, "max_speakers": self.exact}
        values: dict[str, int] = {}
        if self.minimum is not None:
            values["min_speakers"] = self.minimum
        if self.maximum is not None:
            values["max_speakers"] = self.maximum
        return values

    def to_dict(self) -> dict[str, object]:
        return {"exact": self.exact, "minimum": self.minimum, "maximum": self.maximum}

    @classmethod
    def from_dict(cls, payload: Payload) -> Self:
        _expect_keys(payload, {"exact", "minimum", "maximum"})
        return cls(
            exact=_optional_integer(payload["exact"], "exact"),
            minimum=_optional_integer(payload["minimum"], "minimum"),
            maximum=_optional_integer(payload["maximum"], "maximum"),
        )


@dataclass(frozen=True, slots=True)
class InputIdentity:
    """Stable source identity shared by resumable state and canonical output."""

    canonical_path: Path
    size_bytes: int
    mtime_ns: int
    sample_digest: str

    def __post_init__(self) -> None:
        _integer(self.size_bytes, "size_bytes")
        _integer(self.mtime_ns, "mtime_ns")
        if len(self.sample_digest) != 64 or any(
            character not in string.hexdigits for character in self.sample_digest
        ):
            raise ValueError("input identity digest is invalid")

    def to_dict(self) -> dict[str, object]:
        return {
            "canonical_path": str(self.canonical_path),
            "size_bytes": self.size_bytes,
            "mtime_ns": self.mtime_ns,
            "sample_digest": self.sample_digest,
        }

    @classmethod
    def from_dict(cls, payload: Payload) -> Self:
        _expect_keys(payload, {"canonical_path", "size_bytes", "mtime_ns", "sample_digest"})
        return cls(
            canonical_path=_path(payload["canonical_path"], "canonical_path"),
            size_bytes=_integer(payload["size_bytes"], "size_bytes"),
            mtime_ns=_integer(payload["mtime_ns"], "mtime_ns"),
            sample_digest=_string(payload["sample_digest"], "sample_digest"),
        )


@dataclass(frozen=True, slots=True)
class AudioStream:
    index: int
    codec_name: str
    channels: int
    sample_rate_hz: int

    def __post_init__(self) -> None:
        _integer(self.index, "index")
        _string(self.codec_name, "codec_name")
        _integer(self.channels, "channels", minimum=1)
        _integer(self.sample_rate_hz, "sample_rate_hz", minimum=1)

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "codec_name": self.codec_name,
            "channels": self.channels,
            "sample_rate_hz": self.sample_rate_hz,
        }

    @classmethod
    def from_dict(cls, payload: Payload) -> Self:
        _expect_keys(payload, {"index", "codec_name", "channels", "sample_rate_hz"})
        return cls(
            index=_integer(payload["index"], "index"),
            codec_name=_string(payload["codec_name"], "codec_name"),
            channels=_integer(payload["channels"], "channels", minimum=1),
            sample_rate_hz=_integer(payload["sample_rate_hz"], "sample_rate_hz", minimum=1),
        )


@dataclass(frozen=True, slots=True)
class AudioMetadata:
    duration_s: float
    format_name: str
    size_bytes: int
    streams: tuple[AudioStream, ...]

    def __post_init__(self) -> None:
        _number(self.duration_s, "duration_s")
        _string(self.format_name, "format_name")
        _integer(self.size_bytes, "size_bytes")
        if not self.streams:
            raise ValueError("streams must not be empty")

    def to_dict(self) -> dict[str, object]:
        return {
            "duration_s": self.duration_s,
            "format_name": self.format_name,
            "size_bytes": self.size_bytes,
            "streams": [stream.to_dict() for stream in self.streams],
        }

    @classmethod
    def from_dict(cls, payload: Payload) -> Self:
        _expect_keys(payload, {"duration_s", "format_name", "size_bytes", "streams"})
        return cls(
            duration_s=_number(payload["duration_s"], "duration_s"),
            format_name=_string(payload["format_name"], "format_name"),
            size_bytes=_integer(payload["size_bytes"], "size_bytes"),
            streams=tuple(
                AudioStream.from_dict(_mapping(item, "streams item"))
                for item in _list(payload["streams"], "streams")
            ),
        )


@dataclass(frozen=True, slots=True)
class AudioWindow:
    id: str
    start_s: float
    end_s: float
    overlap_before_s: float
    overlap_after_s: float

    def __post_init__(self) -> None:
        _string(self.id, "id")
        _timestamp_pair(_number(self.start_s, "start_s"), _number(self.end_s, "end_s"))
        _number(self.overlap_before_s, "overlap_before_s")
        _number(self.overlap_after_s, "overlap_after_s")

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "start_s": self.start_s,
            "end_s": self.end_s,
            "overlap_before_s": self.overlap_before_s,
            "overlap_after_s": self.overlap_after_s,
        }

    @classmethod
    def from_dict(cls, payload: Payload) -> Self:
        _expect_keys(payload, {"id", "start_s", "end_s", "overlap_before_s", "overlap_after_s"})
        return cls(
            id=_string(payload["id"], "id"),
            start_s=_number(payload["start_s"], "start_s"),
            end_s=_number(payload["end_s"], "end_s"),
            overlap_before_s=_number(payload["overlap_before_s"], "overlap_before_s"),
            overlap_after_s=_number(payload["overlap_after_s"], "overlap_after_s"),
        )


@dataclass(frozen=True, slots=True)
class AudioChunk:
    window: AudioWindow
    path: Path
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        _integer(self.size_bytes, "size_bytes")
        if len(self.sha256) != 64 or any(
            character not in string.hexdigits for character in self.sha256
        ):
            raise ValueError("sha256 must be a 64-character hexadecimal digest")

    def to_dict(self) -> dict[str, object]:
        return {
            "window": self.window.to_dict(),
            "path": str(self.path),
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }

    @classmethod
    def from_dict(cls, payload: Payload) -> Self:
        _expect_keys(payload, {"window", "path", "size_bytes", "sha256"})
        return cls(
            window=AudioWindow.from_dict(_mapping(payload["window"], "window")),
            path=_path(payload["path"], "path"),
            size_bytes=_integer(payload["size_bytes"], "size_bytes"),
            sha256=_string(payload["sha256"], "sha256"),
        )


@dataclass(frozen=True, slots=True)
class ASROptions:
    model: str
    language: str | None
    word_timestamps: bool = True
    condition_on_previous_text: bool = False
    temperature: float = 0.0
    beam_size: int | None = None

    def __post_init__(self) -> None:
        _string(self.model, "model")
        if self.language is not None:
            _string(self.language, "language")
        temperature = _number(self.temperature, "temperature")
        if temperature > 1.0:
            raise ValueError("temperature must be less than or equal to 1")
        if self.beam_size is not None:
            _integer(self.beam_size, "beam_size", minimum=1)

    def to_dict(self) -> dict[str, object]:
        return {
            "model": self.model,
            "language": self.language,
            "word_timestamps": self.word_timestamps,
            "condition_on_previous_text": self.condition_on_previous_text,
            "temperature": self.temperature,
            "beam_size": self.beam_size,
        }

    @classmethod
    def from_dict(cls, payload: Payload) -> Self:
        _expect_keys(
            payload,
            {
                "model",
                "language",
                "word_timestamps",
                "condition_on_previous_text",
                "temperature",
                "beam_size",
            },
        )
        language = payload["language"]
        if language is not None:
            language = _string(language, "language")
        word_timestamps = payload["word_timestamps"]
        condition_on_previous_text = payload["condition_on_previous_text"]
        if not isinstance(word_timestamps, bool) or not isinstance(
            condition_on_previous_text, bool
        ):
            raise ValueError("ASR option flags must be booleans")
        return cls(
            model=_string(payload["model"], "model"),
            language=language,
            word_timestamps=word_timestamps,
            condition_on_previous_text=condition_on_previous_text,
            temperature=_number(payload["temperature"], "temperature"),
            beam_size=_optional_integer(payload["beam_size"], "beam_size"),
        )


@dataclass(frozen=True, slots=True)
class Word:
    start_s: float
    end_s: float
    text: str
    confidence: float | None
    source_chunk: str

    def __post_init__(self) -> None:
        _timestamp_pair(_number(self.start_s, "start_s"), _number(self.end_s, "end_s"))
        _string(self.text, "text")
        _optional_number(self.confidence, "confidence")
        _string(self.source_chunk, "source_chunk")

    def to_dict(self) -> dict[str, object]:
        return {
            "start_s": self.start_s,
            "end_s": self.end_s,
            "text": self.text,
            "confidence": self.confidence,
            "source_chunk": self.source_chunk,
        }

    @classmethod
    def from_dict(cls, payload: Payload) -> Self:
        _expect_keys(payload, {"start_s", "end_s", "text", "confidence", "source_chunk"})
        return cls(
            start_s=_number(payload["start_s"], "start_s"),
            end_s=_number(payload["end_s"], "end_s"),
            text=_string(payload["text"], "text"),
            confidence=_optional_number(payload["confidence"], "confidence"),
            source_chunk=_string(payload["source_chunk"], "source_chunk"),
        )


@dataclass(frozen=True, slots=True)
class AsrSegment:
    start_s: float
    end_s: float
    text: str
    words: tuple[Word, ...]
    average_log_probability: float | None
    no_speech_probability: float | None

    def __post_init__(self) -> None:
        _timestamp_pair(_number(self.start_s, "start_s"), _number(self.end_s, "end_s"))
        _string(self.text, "text")
        if not self.words:
            raise ValueError("words must not be empty")
        _optional_number(self.average_log_probability, "average_log_probability")
        _optional_number(self.no_speech_probability, "no_speech_probability")

    def to_dict(self) -> dict[str, object]:
        return {
            "start_s": self.start_s,
            "end_s": self.end_s,
            "text": self.text,
            "words": [word.to_dict() for word in self.words],
            "average_log_probability": self.average_log_probability,
            "no_speech_probability": self.no_speech_probability,
        }

    @classmethod
    def from_dict(cls, payload: Payload) -> Self:
        _expect_keys(
            payload,
            {
                "start_s",
                "end_s",
                "text",
                "words",
                "average_log_probability",
                "no_speech_probability",
            },
        )
        return cls(
            start_s=_number(payload["start_s"], "start_s"),
            end_s=_number(payload["end_s"], "end_s"),
            text=_string(payload["text"], "text"),
            words=tuple(
                Word.from_dict(_mapping(item, "words item"))
                for item in _list(payload["words"], "words")
            ),
            average_log_probability=_optional_number(
                payload["average_log_probability"], "average_log_probability"
            ),
            no_speech_probability=_optional_number(
                payload["no_speech_probability"], "no_speech_probability"
            ),
        )


@dataclass(frozen=True, slots=True)
class ASRChunkResult:
    chunk: AudioChunk
    backend: str
    model: str
    language: str | None
    segments: tuple[AsrSegment, ...]
    no_speech_probability: float | None = None

    def __post_init__(self) -> None:
        _string(self.backend, "backend")
        _string(self.model, "model")
        if self.language is not None:
            _string(self.language, "language")
        if self.no_speech_probability is not None:
            probability = _number(self.no_speech_probability, "no_speech_probability")
            if probability > 1:
                raise ValueError("no_speech_probability must not exceed one")

    def to_dict(self) -> dict[str, object]:
        return {
            "chunk": self.chunk.to_dict(),
            "backend": self.backend,
            "model": self.model,
            "language": self.language,
            "segments": [segment.to_dict() for segment in self.segments],
            "no_speech_probability": self.no_speech_probability,
        }

    @classmethod
    def from_dict(cls, payload: Payload) -> Self:
        _expect_keys(
            payload,
            {"chunk", "backend", "model", "language", "segments", "no_speech_probability"},
        )
        language = payload["language"]
        if language is not None:
            language = _string(language, "language")
        return cls(
            chunk=AudioChunk.from_dict(_mapping(payload["chunk"], "chunk")),
            backend=_string(payload["backend"], "backend"),
            model=_string(payload["model"], "model"),
            language=language,
            segments=tuple(
                AsrSegment.from_dict(_mapping(item, "segments item"))
                for item in _list(payload["segments"], "segments")
            ),
            no_speech_probability=_optional_number(
                payload["no_speech_probability"], "no_speech_probability"
            ),
        )


@dataclass(frozen=True, slots=True)
class ChunkingProvenance:
    max_duration_s: float
    overlap_s: float

    def __post_init__(self) -> None:
        maximum = _number(self.max_duration_s, "max_duration_s")
        overlap = _number(self.overlap_s, "overlap_s")
        if overlap >= maximum:
            raise ValueError("chunking overlap must be smaller than the maximum duration")

    def to_dict(self) -> dict[str, object]:
        return {"max_duration_s": self.max_duration_s, "overlap_s": self.overlap_s}

    @classmethod
    def from_dict(cls, payload: Payload) -> Self:
        _expect_keys(payload, {"max_duration_s", "overlap_s"})
        return cls(
            max_duration_s=_number(payload["max_duration_s"], "max_duration_s"),
            overlap_s=_number(payload["overlap_s"], "overlap_s"),
        )


@dataclass(frozen=True, slots=True)
class ASRProvenance:
    mode: Mode
    backend: str
    model: str
    chunking: ChunkingProvenance
    detected_language: str | None

    def __post_init__(self) -> None:
        _string(self.backend, "backend")
        _string(self.model, "model")
        if self.detected_language is not None:
            _string(self.detected_language, "detected_language")

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode.value,
            "backend": self.backend,
            "model": self.model,
            "chunking": self.chunking.to_dict(),
            "detected_language": self.detected_language,
        }

    @classmethod
    def from_dict(cls, payload: Payload) -> Self:
        _expect_keys(payload, {"mode", "backend", "model", "chunking", "detected_language"})
        try:
            mode = Mode(_string(payload["mode"], "mode"))
        except ValueError as exc:
            raise ValueError("ASR mode is invalid") from exc
        language = payload["detected_language"]
        if language is not None:
            language = _string(language, "detected_language")
        return cls(
            mode=mode,
            backend=_string(payload["backend"], "backend"),
            model=_string(payload["model"], "model"),
            chunking=ChunkingProvenance.from_dict(_mapping(payload["chunking"], "chunking")),
            detected_language=language,
        )


@dataclass(frozen=True, slots=True)
class DiarizationProvenance:
    model: str
    revision: str
    compute_device: ComputeDevice
    speaker_count: SpeakerCount

    def __post_init__(self) -> None:
        _string(self.model, "model")
        _string(self.revision, "revision")

    def to_dict(self) -> dict[str, object]:
        return {
            "model": self.model,
            "revision": self.revision,
            "compute_device": self.compute_device.value,
            "speaker_count_parameters": self.speaker_count.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Payload) -> Self:
        _expect_keys(payload, {"model", "revision", "compute_device", "speaker_count_parameters"})
        try:
            compute_device = ComputeDevice(_string(payload["compute_device"], "compute_device"))
        except ValueError as exc:
            raise ValueError("diarization compute device is invalid") from exc
        return cls(
            model=_string(payload["model"], "model"),
            revision=_string(payload["revision"], "revision"),
            compute_device=compute_device,
            speaker_count=SpeakerCount.from_dict(
                _mapping(payload["speaker_count_parameters"], "speaker_count_parameters")
            ),
        )


@dataclass(frozen=True, slots=True)
class TranscriptProvenance:
    runtime_version: str
    run_fingerprint: str
    completed_stages: tuple[StageName, ...]
    retries: tuple[str, ...]

    def __post_init__(self) -> None:
        _string(self.runtime_version, "runtime_version")
        _string(self.run_fingerprint, "run_fingerprint")
        if len(self.run_fingerprint) != 64 or any(
            character not in string.hexdigits for character in self.run_fingerprint
        ):
            raise ValueError("run_fingerprint must be a 64-character hexadecimal digest")
        if len(set(self.completed_stages)) != len(self.completed_stages):
            raise ValueError("completed stages must not repeat")
        if len(set(self.retries)) != len(self.retries):
            raise ValueError("retries must not repeat")
        for retry in self.retries:
            _string(retry, "retries item")

    def to_dict(self) -> dict[str, object]:
        return {
            "runtime_version": self.runtime_version,
            "run_fingerprint": self.run_fingerprint,
            "completed_stages": [stage.value for stage in self.completed_stages],
            "retries": list(self.retries),
        }

    @classmethod
    def from_dict(cls, payload: Payload) -> Self:
        _expect_keys(payload, {"runtime_version", "run_fingerprint", "completed_stages", "retries"})
        stages: list[StageName] = []
        for stage in _list(payload["completed_stages"], "completed_stages"):
            try:
                stages.append(StageName(_string(stage, "completed_stages item")))
            except ValueError as exc:
                raise ValueError("completed stage is invalid") from exc
        return cls(
            runtime_version=_string(payload["runtime_version"], "runtime_version"),
            run_fingerprint=_string(payload["run_fingerprint"], "run_fingerprint"),
            completed_stages=tuple(stages),
            retries=tuple(
                _string(retry, "retries item") for retry in _list(payload["retries"], "retries")
            ),
        )


@dataclass(frozen=True, slots=True)
class DiarizationTurn:
    start_s: float
    end_s: float
    raw_speaker: str

    def __post_init__(self) -> None:
        _timestamp_pair(_number(self.start_s, "start_s"), _number(self.end_s, "end_s"))
        _string(self.raw_speaker, "raw_speaker")

    def to_dict(self) -> dict[str, object]:
        return {"start_s": self.start_s, "end_s": self.end_s, "raw_speaker": self.raw_speaker}

    @classmethod
    def from_dict(cls, payload: Payload) -> Self:
        _expect_keys(payload, {"start_s", "end_s", "raw_speaker"})
        return cls(
            start_s=_number(payload["start_s"], "start_s"),
            end_s=_number(payload["end_s"], "end_s"),
            raw_speaker=_string(payload["raw_speaker"], "raw_speaker"),
        )


@dataclass(frozen=True, slots=True)
class AlignedWord:
    word: Word
    raw_speaker: str
    speaker: str

    def __post_init__(self) -> None:
        _string(self.raw_speaker, "raw_speaker")
        _string(self.speaker, "speaker")

    def to_dict(self) -> dict[str, object]:
        return {
            "word": self.word.to_dict(),
            "raw_speaker": self.raw_speaker,
            "speaker": self.speaker,
        }

    @classmethod
    def from_dict(cls, payload: Payload) -> Self:
        _expect_keys(payload, {"word", "raw_speaker", "speaker"})
        return cls(
            word=Word.from_dict(_mapping(payload["word"], "word")),
            raw_speaker=_string(payload["raw_speaker"], "raw_speaker"),
            speaker=_string(payload["speaker"], "speaker"),
        )


@dataclass(frozen=True, slots=True)
class TranscriptTurn:
    start_s: float
    end_s: float
    raw_speaker: str
    speaker: str
    text: str
    words: tuple[AlignedWord, ...]

    def __post_init__(self) -> None:
        _timestamp_pair(_number(self.start_s, "start_s"), _number(self.end_s, "end_s"))
        _string(self.raw_speaker, "raw_speaker")
        _string(self.speaker, "speaker")
        _string(self.text, "text")
        if not self.words:
            raise ValueError("words must not be empty")

    def to_dict(self) -> dict[str, object]:
        return {
            "start_s": self.start_s,
            "end_s": self.end_s,
            "raw_speaker": self.raw_speaker,
            "speaker": self.speaker,
            "text": self.text,
            "words": [word.to_dict() for word in self.words],
        }

    @classmethod
    def from_dict(cls, payload: Payload) -> Self:
        _expect_keys(payload, {"start_s", "end_s", "raw_speaker", "speaker", "text", "words"})
        return cls(
            start_s=_number(payload["start_s"], "start_s"),
            end_s=_number(payload["end_s"], "end_s"),
            raw_speaker=_string(payload["raw_speaker"], "raw_speaker"),
            speaker=_string(payload["speaker"], "speaker"),
            text=_string(payload["text"], "text"),
            words=tuple(
                AlignedWord.from_dict(_mapping(item, "words item"))
                for item in _list(payload["words"], "words")
            ),
        )


@dataclass(frozen=True, slots=True)
class QualityIssue:
    code: str
    severity: Literal["warning", "error"]
    start_s: float
    end_s: float
    chunk_ids: tuple[str, ...]
    detail: str

    def __post_init__(self) -> None:
        _string(self.code, "code")
        if self.severity not in {"warning", "error"}:
            raise ValueError("severity must be warning or error")
        _timestamp_pair(_number(self.start_s, "start_s"), _number(self.end_s, "end_s"))
        if not self.chunk_ids:
            raise ValueError("chunk_ids must not be empty")
        for chunk_id in self.chunk_ids:
            _string(chunk_id, "chunk_ids item")
        _string(self.detail, "detail")

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "severity": self.severity,
            "start_s": self.start_s,
            "end_s": self.end_s,
            "chunk_ids": list(self.chunk_ids),
            "detail": self.detail,
        }

    @classmethod
    def from_dict(cls, payload: Payload) -> Self:
        _expect_keys(payload, {"code", "severity", "start_s", "end_s", "chunk_ids", "detail"})
        severity_value = payload["severity"]
        if severity_value == "warning":
            severity: Literal["warning", "error"] = "warning"
        elif severity_value == "error":
            severity = "error"
        else:
            raise ValueError("severity must be warning or error")
        return cls(
            code=_string(payload["code"], "code"),
            severity=severity,
            start_s=_number(payload["start_s"], "start_s"),
            end_s=_number(payload["end_s"], "end_s"),
            chunk_ids=tuple(
                _string(item, "chunk_ids item") for item in _list(payload["chunk_ids"], "chunk_ids")
            ),
            detail=_string(payload["detail"], "detail"),
        )


@dataclass(frozen=True, slots=True)
class QualityCheckResult:
    code: str
    status: Literal["passed", "warning", "failed", "not_applicable"]
    detail: str

    def __post_init__(self) -> None:
        _string(self.code, "code")
        if self.status not in {"passed", "warning", "failed", "not_applicable"}:
            raise ValueError("status is invalid")
        _string(self.detail, "detail")

    def to_dict(self) -> dict[str, object]:
        return {"code": self.code, "status": self.status, "detail": self.detail}

    @classmethod
    def from_dict(cls, payload: Payload) -> Self:
        _expect_keys(payload, {"code", "status", "detail"})
        status_value = payload["status"]
        if status_value == "passed":
            status: Literal["passed", "warning", "failed", "not_applicable"] = "passed"
        elif status_value == "warning":
            status = "warning"
        elif status_value == "failed":
            status = "failed"
        elif status_value == "not_applicable":
            status = "not_applicable"
        else:
            raise ValueError("status is invalid")
        return cls(
            code=_string(payload["code"], "code"),
            status=status,
            detail=_string(payload["detail"], "detail"),
        )


@dataclass(frozen=True, slots=True)
class QualityReport:
    policy_version: str
    status: Literal["passed", "failed"]
    checks: tuple[QualityCheckResult, ...]
    warnings: tuple[QualityIssue, ...]
    unresolved_errors: tuple[QualityIssue, ...]

    def __post_init__(self) -> None:
        _string(self.policy_version, "policy_version")
        if self.status not in {"passed", "failed"}:
            raise ValueError("status must be passed or failed")

    def to_dict(self) -> dict[str, object]:
        return {
            "policy_version": self.policy_version,
            "status": self.status,
            "checks": [check.to_dict() for check in self.checks],
            "warnings": [warning.to_dict() for warning in self.warnings],
            "unresolved_errors": [error.to_dict() for error in self.unresolved_errors],
        }

    @classmethod
    def from_dict(cls, payload: Payload) -> Self:
        _expect_keys(
            payload, {"policy_version", "status", "checks", "warnings", "unresolved_errors"}
        )
        status_value = payload["status"]
        if status_value == "passed":
            status: Literal["passed", "failed"] = "passed"
        elif status_value == "failed":
            status = "failed"
        else:
            raise ValueError("status must be passed or failed")
        return cls(
            policy_version=_string(payload["policy_version"], "policy_version"),
            status=status,
            checks=tuple(
                QualityCheckResult.from_dict(_mapping(item, "checks item"))
                for item in _list(payload["checks"], "checks")
            ),
            warnings=tuple(
                QualityIssue.from_dict(_mapping(item, "warnings item"))
                for item in _list(payload["warnings"], "warnings")
            ),
            unresolved_errors=tuple(
                QualityIssue.from_dict(_mapping(item, "unresolved_errors item"))
                for item in _list(payload["unresolved_errors"], "unresolved_errors")
            ),
        )


@dataclass(frozen=True, slots=True)
class TranscriptSpeaker:
    raw_label: str
    display_name: str

    def __post_init__(self) -> None:
        _string(self.raw_label, "raw_label")
        _string(self.display_name, "display_name")

    def to_dict(self) -> dict[str, object]:
        return {"raw_label": self.raw_label, "display_name": self.display_name}

    @classmethod
    def from_dict(cls, payload: Payload) -> Self:
        _expect_keys(payload, {"raw_label", "display_name"})
        return cls(
            raw_label=_string(payload["raw_label"], "raw_label"),
            display_name=_string(payload["display_name"], "display_name"),
        )


@dataclass(frozen=True, slots=True)
class TranscriptDocument:
    schema_version: int
    input_identity: InputIdentity
    duration_s: float
    language: str | None
    asr: ASRProvenance
    diarization: DiarizationProvenance
    provenance: TranscriptProvenance
    speakers: tuple[TranscriptSpeaker, ...]
    turns: tuple[TranscriptTurn, ...]
    quality: QualityReport

    def __post_init__(self) -> None:
        if self.schema_version != OUTPUT_SCHEMA_VERSION:
            raise ValueError(f"transcript schema version must be {OUTPUT_SCHEMA_VERSION}")
        _number(self.duration_s, "duration_s")
        if self.language is not None:
            _string(self.language, "language")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "input": {
                "canonical_path": str(self.input_identity.canonical_path),
                "size": self.input_identity.size_bytes,
                "mtime_ns": self.input_identity.mtime_ns,
                "sample_digest": self.input_identity.sample_digest,
                "duration_s": self.duration_s,
            },
            "language": self.language,
            "asr": self.asr.to_dict(),
            "diarization": self.diarization.to_dict(),
            "provenance": self.provenance.to_dict(),
            "speakers": [speaker.to_dict() for speaker in self.speakers],
            "turns": [turn.to_dict() for turn in self.turns],
            "quality": self.quality.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Payload) -> Self:
        _expect_keys(
            payload,
            {
                "schema_version",
                "input",
                "language",
                "asr",
                "diarization",
                "provenance",
                "speakers",
                "turns",
                "quality",
            },
        )
        input_payload = _mapping(payload["input"], "input")
        _expect_keys(
            input_payload,
            {"canonical_path", "size", "mtime_ns", "sample_digest", "duration_s"},
        )
        language = payload["language"]
        if language is not None:
            language = _string(language, "language")
        return cls(
            schema_version=_integer(payload["schema_version"], "schema_version", minimum=1),
            input_identity=InputIdentity(
                canonical_path=_path(input_payload["canonical_path"], "canonical_path"),
                size_bytes=_integer(input_payload["size"], "input size"),
                mtime_ns=_integer(input_payload["mtime_ns"], "input mtime_ns"),
                sample_digest=_string(input_payload["sample_digest"], "input sample_digest"),
            ),
            duration_s=_number(input_payload["duration_s"], "input duration_s"),
            language=language,
            asr=ASRProvenance.from_dict(_mapping(payload["asr"], "asr")),
            diarization=DiarizationProvenance.from_dict(
                _mapping(payload["diarization"], "diarization")
            ),
            provenance=TranscriptProvenance.from_dict(
                _mapping(payload["provenance"], "provenance")
            ),
            speakers=tuple(
                TranscriptSpeaker.from_dict(_mapping(speaker, "speakers item"))
                for speaker in _list(payload["speakers"], "speakers")
            ),
            turns=tuple(
                TranscriptTurn.from_dict(_mapping(turn, "turns item"))
                for turn in _list(payload["turns"], "turns")
            ),
            quality=QualityReport.from_dict(_mapping(payload["quality"], "quality")),
        )


@dataclass(frozen=True, slots=True)
class UploadConsent:
    provider: Literal["openai"]
    granted: bool
    interactive: bool

    def __post_init__(self) -> None:
        if self.provider != "openai":
            raise ValueError("provider must be openai")


@dataclass(frozen=True, slots=True)
class OutputPaths:
    json: Path
    txt: Path
    srt: Path | None
    vtt: Path | None

    def to_dict(self) -> dict[str, object]:
        return {
            "json": str(self.json),
            "txt": str(self.txt),
            "srt": str(self.srt) if self.srt is not None else None,
            "vtt": str(self.vtt) if self.vtt is not None else None,
        }

    @classmethod
    def from_dict(cls, payload: Payload) -> Self:
        _expect_keys(payload, {"json", "txt", "srt", "vtt"})
        return cls(
            json=_path(payload["json"], "json"),
            txt=_path(payload["txt"], "txt"),
            srt=_optional_path(payload["srt"], "srt"),
            vtt=_optional_path(payload["vtt"], "vtt"),
        )
