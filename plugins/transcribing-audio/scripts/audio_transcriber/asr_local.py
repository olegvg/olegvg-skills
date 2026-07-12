"""Injected MLX and faster-whisper adapters with one timestamped word contract."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import cast

from .errors import SafeError
from .models import (
    ASRChunkResult,
    ASROptions,
    AsrSegment,
    AudioChunk,
    BackendFamily,
    StageName,
    Word,
)


def _require_options(options: ASROptions, backend: str, chunk: AudioChunk) -> None:
    if not options.word_timestamps:
        raise SafeError(
            stage=StageName.ASR,
            message="word timestamps are required for transcription",
            start_s=chunk.window.start_s,
            end_s=chunk.window.end_s,
            backend=backend,
        )
    if options.condition_on_previous_text:
        raise SafeError(
            stage=StageName.ASR,
            message="previous-text conditioning is forbidden for independent chunks",
            start_s=chunk.window.start_s,
            end_s=chunk.window.end_s,
            backend=backend,
        )


def _mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} is invalid")
    raw_mapping = cast(Mapping[object, object], value)
    if not all(isinstance(key, str) for key in raw_mapping):
        raise ValueError(f"{field} is invalid")
    return {cast(str, key): item for key, item in raw_mapping.items()}


def _value(source: object, field: str) -> object:
    if isinstance(source, Mapping):
        return cast(Mapping[str, object], source).get(field)
    return cast(object, getattr(source, field, None))


def _number(value: object, field: str, *, nullable: bool = False) -> float | None:
    if value is None and nullable:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} is invalid")
    return float(value)


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} is invalid")
    return value


def _iterable(value: object, field: str) -> Iterable[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
        raise ValueError(f"{field} is invalid")
    return cast(Iterable[object], value)


def _parse_words(value: object, chunk_id: str) -> tuple[Word, ...]:
    words: list[Word] = []
    for raw_word in _iterable(value, "backend words"):
        words.append(
            Word(
                start_s=cast(float, _number(_value(raw_word, "start"), "word start")),
                end_s=cast(float, _number(_value(raw_word, "end"), "word end")),
                text=_text(_value(raw_word, "word"), "word text"),
                confidence=_number(
                    _value(raw_word, "probability"), "word probability", nullable=True
                ),
                source_chunk=chunk_id,
            )
        )
    return tuple(words)


def _parse_segments(value: object, chunk_id: str) -> tuple[tuple[AsrSegment, ...], float | None]:
    segments: list[AsrSegment] = []
    no_speech_probabilities: list[float] = []
    for raw_segment in _iterable(value, "backend segments"):
        words = _parse_words(_value(raw_segment, "words"), chunk_id)
        no_speech_probability = _number(
            _value(raw_segment, "no_speech_prob"), "segment no_speech_prob", nullable=True
        )
        if no_speech_probability is not None:
            no_speech_probabilities.append(no_speech_probability)
        if not words:
            continue
        segments.append(
            AsrSegment(
                start_s=cast(float, _number(_value(raw_segment, "start"), "segment start")),
                end_s=cast(float, _number(_value(raw_segment, "end"), "segment end")),
                text=_text(_value(raw_segment, "text"), "segment text"),
                words=words,
                average_log_probability=_number(
                    _value(raw_segment, "avg_logprob"), "segment avg_logprob", nullable=True
                ),
                no_speech_probability=no_speech_probability,
            )
        )
    return tuple(segments), max(no_speech_probabilities, default=None)


class MlxASR:
    """Lazy MLX adapter; imports are supplied through a factory for testability."""

    def __init__(self, transcriber_factory: Callable[[], Callable[..., object]]) -> None:
        self._transcriber_factory = transcriber_factory
        self._transcriber: Callable[..., object] | None = None
        self._model: str | None = None

    def transcribe(self, chunk: AudioChunk, options: ASROptions) -> ASRChunkResult:
        backend = BackendFamily.MLX.value
        _require_options(options, backend, chunk)
        try:
            if self._transcriber is None:
                self._transcriber = self._transcriber_factory()
                self._model = options.model
            elif self._model != options.model:
                raise ValueError("an adapter instance cannot change models")
            response = self._transcriber(
                str(chunk.path),
                path_or_hf_repo=options.model,
                language=options.language,
                word_timestamps=True,
                condition_on_previous_text=False,
                temperature=options.temperature,
                beam_size=options.beam_size,
            )
            payload = _mapping(response, "MLX response")
            language_value = payload.get("language")
            language = (
                language_value
                if isinstance(language_value, str) and language_value
                else options.language
            )
            segments, no_speech_probability = _parse_segments(
                payload.get("segments"), chunk.window.id
            )
            return ASRChunkResult(
                chunk=chunk,
                backend=backend,
                model=options.model,
                language=language,
                segments=segments,
                no_speech_probability=no_speech_probability,
            )
        except SafeError:
            raise
        except Exception as exc:
            raise SafeError(
                stage=StageName.ASR,
                message="local MLX transcription failed",
                start_s=chunk.window.start_s,
                end_s=chunk.window.end_s,
                backend=backend,
                recovery_hint="retry the affected chunk with the approved fallback backend",
            ) from exc

    def health_check(self, model: str) -> None:
        """Load the local callable before audio processing begins."""
        if not model:
            raise ValueError("model must be non-empty")
        try:
            if self._transcriber is None:
                self._transcriber = self._transcriber_factory()
                self._model = model
            elif self._model != model:
                raise ValueError("an adapter instance cannot change models")
        except Exception as exc:
            raise SafeError(
                stage=StageName.ASR,
                message="local MLX model startup failed",
                backend=BackendFamily.MLX.value,
            ) from exc


class FasterWhisperASR:
    """Lazy CUDA/CPU faster-whisper adapter that exhausts the segment generator safely."""

    def __init__(
        self,
        model_factory: Callable[[str, str, str], object],
        backend: BackendFamily,
        *,
        cuda_compute_type: str,
    ) -> None:
        if backend not in {BackendFamily.CUDA, BackendFamily.CPU}:
            raise ValueError("faster-whisper supports only CUDA or CPU backends")
        if not cuda_compute_type:
            raise ValueError("CUDA compute type must be non-empty")
        self._model_factory = model_factory
        self._backend = backend
        self._cuda_compute_type = cuda_compute_type
        self._model: object | None = None
        self._model_name: str | None = None

    def transcribe(self, chunk: AudioChunk, options: ASROptions) -> ASRChunkResult:
        backend = self._backend.value
        _require_options(options, backend, chunk)
        try:
            if self._model is None:
                device = "cuda" if self._backend is BackendFamily.CUDA else "cpu"
                compute_type = self._cuda_compute_type if device == "cuda" else "int8"
                self._model = self._model_factory(options.model, device, compute_type)
                self._model_name = options.model
            elif self._model_name != options.model:
                raise ValueError("an adapter instance cannot change models")
            transcribe = getattr(self._model, "transcribe", None)
            if not callable(transcribe):
                raise ValueError("faster-whisper model has no transcribe method")
            response = transcribe(
                str(chunk.path),
                language=options.language,
                word_timestamps=True,
                condition_on_previous_text=False,
                temperature=options.temperature,
                beam_size=options.beam_size,
            )
            if not isinstance(response, tuple):
                raise ValueError("faster-whisper response is invalid")
            response_tuple = cast(tuple[object, ...], response)
            if len(response_tuple) != 2:
                raise ValueError("faster-whisper response is invalid")
            raw_segments, info = response_tuple
            segments, no_speech_probability = _parse_segments(
                tuple(_iterable(raw_segments, "faster-whisper segments")), chunk.window.id
            )
            language_value = _value(info, "language")
            language = (
                language_value
                if isinstance(language_value, str) and language_value
                else options.language
            )
            return ASRChunkResult(
                chunk=chunk,
                backend=backend,
                model=options.model,
                language=language,
                segments=segments,
                no_speech_probability=no_speech_probability,
            )
        except SafeError:
            raise
        except Exception as exc:
            raise SafeError(
                stage=StageName.ASR,
                message="local faster-whisper transcription failed",
                start_s=chunk.window.start_s,
                end_s=chunk.window.end_s,
                backend=backend,
                recovery_hint="retry the affected chunk with the approved fallback backend",
            ) from exc

    def health_check(self, model: str) -> None:
        """Initialize the selected local model without reading an audio chunk."""
        if not model:
            raise ValueError("model must be non-empty")
        try:
            if self._model is None:
                device = "cuda" if self._backend is BackendFamily.CUDA else "cpu"
                compute_type = self._cuda_compute_type if device == "cuda" else "int8"
                self._model = self._model_factory(model, device, compute_type)
                self._model_name = model
            elif self._model_name != model:
                raise ValueError("an adapter instance cannot change models")
        except Exception as exc:
            raise SafeError(
                stage=StageName.ASR,
                message="local faster-whisper model startup failed",
                backend=self._backend.value,
            ) from exc
