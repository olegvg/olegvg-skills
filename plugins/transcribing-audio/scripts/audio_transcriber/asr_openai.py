"""Consent-gated OpenAI word-timestamp transcription adapter."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import cast

from .constants import DEFAULT_MAX_UPLOAD_BYTES
from .errors import SafeError
from .models import (
    ASRChunkResult,
    ASROptions,
    AsrSegment,
    AudioChunk,
    StageName,
    UploadConsent,
    Word,
)

_WORD_TIMESTAMP_MODELS = frozenset({"whisper-1"})


def _attribute(value: object, name: str) -> object:
    return cast(object, getattr(value, name, None))


def _field(value: object, name: str) -> object:
    if isinstance(value, Mapping):
        return cast(Mapping[str, object], value).get(name)
    return _attribute(value, name)


def _iterable(value: object, field: str) -> tuple[object, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
        raise ValueError(f"OpenAI {field} is invalid")
    return tuple(cast(Iterable[object], value))


def _number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"OpenAI {field} is invalid")
    return float(value)


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"OpenAI {field} is invalid")
    return value


class OpenAIASR:
    """Adapts only the documented `whisper-1` verbose word-timestamp response."""

    def __init__(
        self,
        client: object,
        *,
        api_key: str | None,
        consent: UploadConsent,
        max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
    ) -> None:
        if max_upload_bytes <= 0:
            raise ValueError("OpenAI upload ceiling must be positive")
        self._client = client
        self._api_key = api_key
        self._consent = consent
        self._max_upload_bytes = max_upload_bytes

    def __repr__(self) -> str:
        return "OpenAIASR(client=<redacted>, api_key=<redacted>)"

    def _preflight(self, chunk: AudioChunk, options: ASROptions) -> None:
        if not self._consent.granted:
            raise SafeError(
                stage=StageName.ASR,
                message="explicit consent is required before uploading audio to OpenAI",
                start_s=chunk.window.start_s,
                end_s=chunk.window.end_s,
                backend="openai",
            )
        if not self._api_key:
            raise SafeError(
                stage=StageName.ASR,
                message="OpenAI API key is required before opening audio",
                start_s=chunk.window.start_s,
                end_s=chunk.window.end_s,
                backend="openai",
            )
        if options.model not in _WORD_TIMESTAMP_MODELS:
            raise SafeError(
                stage=StageName.ASR,
                message="selected OpenAI model does not support mandatory verbose word timestamps",
                start_s=chunk.window.start_s,
                end_s=chunk.window.end_s,
                backend="openai",
            )
        try:
            size_bytes = chunk.path.stat().st_size
        except OSError as exc:
            raise SafeError(
                stage=StageName.ASR,
                message="audio chunk cannot be inspected before upload",
                start_s=chunk.window.start_s,
                end_s=chunk.window.end_s,
                backend="openai",
            ) from exc
        if size_bytes >= self._max_upload_bytes:
            raise SafeError(
                stage=StageName.ASR,
                message="audio chunk exceeds the configured OpenAI upload size ceiling",
                start_s=chunk.window.start_s,
                end_s=chunk.window.end_s,
                backend="openai",
            )
        if not options.word_timestamps or options.condition_on_previous_text:
            raise SafeError(
                stage=StageName.ASR,
                message="independent transcription requires mandatory word timestamps",
                start_s=chunk.window.start_s,
                end_s=chunk.window.end_s,
                backend="openai",
            )

    def health_check(self, model: str) -> None:
        """Validate local OpenAI prerequisites without contacting the provider."""
        if not self._consent.granted:
            raise SafeError(
                stage=StageName.ASR,
                message="explicit consent is required before uploading audio to OpenAI",
                backend="openai",
            )
        if not self._api_key:
            raise SafeError(
                stage=StageName.ASR,
                message="OpenAI API key is required before uploading audio",
                backend="openai",
            )
        if model not in _WORD_TIMESTAMP_MODELS:
            raise SafeError(
                stage=StageName.ASR,
                message="selected OpenAI model does not support mandatory verbose word timestamps",
                backend="openai",
            )

    def _create(self) -> Callable[..., object]:
        audio = _attribute(self._client, "audio")
        transcriptions = _attribute(audio, "transcriptions")
        create = _attribute(transcriptions, "create")
        if not callable(create):
            raise ValueError("OpenAI client has no transcription create method")
        return create

    @staticmethod
    def _parse_words(value: object, chunk_id: str) -> tuple[Word, ...]:
        words: list[Word] = []
        for raw_word in _iterable(value, "word timestamps"):
            words.append(
                Word(
                    start_s=_number(_field(raw_word, "start"), "word start"),
                    end_s=_number(_field(raw_word, "end"), "word end"),
                    text=_text(_field(raw_word, "word"), "word text"),
                    confidence=None,
                    source_chunk=chunk_id,
                )
            )
        return tuple(words)

    @staticmethod
    def _segments(value: object, words: tuple[Word, ...]) -> tuple[AsrSegment, ...]:
        if value is None:
            if not words:
                return ()
            return (
                AsrSegment(
                    start_s=words[0].start_s,
                    end_s=words[-1].end_s,
                    text=" ".join(word.text for word in words),
                    words=words,
                    average_log_probability=None,
                    no_speech_probability=None,
                ),
            )
        parsed: list[AsrSegment] = []
        for raw_segment in _iterable(value, "segments"):
            start_s = _number(_field(raw_segment, "start"), "segment start")
            end_s = _number(_field(raw_segment, "end"), "segment end")
            segment_words = tuple(
                word for word in words if start_s <= (word.start_s + word.end_s) / 2 <= end_s
            )
            if not segment_words:
                continue
            raw_text = _field(raw_segment, "text")
            text = (
                raw_text
                if isinstance(raw_text, str) and raw_text
                else " ".join(word.text for word in segment_words)
            )
            parsed.append(
                AsrSegment(
                    start_s=start_s,
                    end_s=end_s,
                    text=text,
                    words=segment_words,
                    average_log_probability=None,
                    no_speech_probability=None,
                )
            )
        if words and not parsed:
            raise ValueError("OpenAI segments do not cover mandatory word timestamps")
        return tuple(parsed)

    def transcribe(self, chunk: AudioChunk, options: ASROptions) -> ASRChunkResult:
        self._preflight(chunk, options)
        try:
            with chunk.path.open("rb") as audio_file:
                request: dict[str, object] = {
                    "model": options.model,
                    "file": audio_file,
                    "response_format": "verbose_json",
                    "timestamp_granularities": ["word", "segment"],
                    "temperature": 0,
                }
                if options.language is not None:
                    request["language"] = options.language
                response = self._create()(**request)
            words = self._parse_words(_field(response, "words"), chunk.window.id)
            text = _field(response, "text")
            if isinstance(text, str) and text.strip() and not words:
                raise ValueError("OpenAI response omitted mandatory word timestamps")
            language_value = _field(response, "language")
            language = (
                language_value
                if isinstance(language_value, str) and language_value
                else options.language
            )
            return ASRChunkResult(
                chunk=chunk,
                backend="openai",
                model=options.model,
                language=language,
                segments=self._segments(_field(response, "segments"), words),
            )
        except SafeError:
            raise
        except ValueError as exc:
            raise SafeError(
                stage=StageName.ASR,
                message="OpenAI response did not provide mandatory word timestamps",
                start_s=chunk.window.start_s,
                end_s=chunk.window.end_s,
                backend="openai",
                recovery_hint="retry the affected chunk after checking the provider response format",
            ) from exc
        except Exception as exc:
            raise SafeError(
                stage=StageName.ASR,
                message="OpenAI transcription failed",
                start_s=chunk.window.start_s,
                end_s=chunk.window.end_s,
                backend="openai",
                recovery_hint="retry the affected chunk after checking provider availability",
            ) from exc
