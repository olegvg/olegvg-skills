from __future__ import annotations

from pathlib import Path

import pytest

from audio_transcriber.asr_openai import OpenAIASR
from audio_transcriber.errors import SafeError
from audio_transcriber.models import ASROptions, AudioChunk, AudioWindow, UploadConsent


def _chunk(path: Path) -> AudioChunk:
    path.write_bytes(b"flac")
    return AudioChunk(AudioWindow("chunk-0000", 0, 2, 0, 0), path, 4, "a" * 64)


class Client:
    def __init__(self, response: object | Exception) -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []
        self.audio = self
        self.transcriptions = self

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _response() -> dict[str, object]:
    return {
        "language": "ru",
        "text": "привет мир",
        "words": [
            {"start": 0.0, "end": 0.4, "word": "привет"},
            {"start": 0.5, "end": 0.9, "word": "мир"},
        ],
        "segments": [{"start": 0.0, "end": 0.9, "text": "привет мир"}],
    }


def test_openai_requires_explicit_granted_consent_and_key_before_file_open(tmp_path: Path) -> None:
    source = tmp_path / "chunk.flac"
    client = Client(_response())
    denied = OpenAIASR(client, api_key="sk-test", consent=UploadConsent("openai", False, True))

    with pytest.raises(SafeError) as denied_error:
        denied.transcribe(_chunk(source), ASROptions("whisper-1", "ru"))
    assert "consent" in denied_error.value.render({"sk-test"})
    assert client.calls == []

    no_key = OpenAIASR(client, api_key=None, consent=UploadConsent("openai", True, False))
    with pytest.raises(SafeError) as key_error:
        no_key.transcribe(_chunk(source), ASROptions("whisper-1", "ru"))
    assert "API key" in key_error.value.render(set())
    assert client.calls == []


def test_openai_requests_verbose_word_timestamps_and_keeps_relative_offsets(tmp_path: Path) -> None:
    source = tmp_path / "chunk.flac"
    client = Client(_response())
    adapter = OpenAIASR(client, api_key="sk-test", consent=UploadConsent("openai", True, False))

    result = adapter.transcribe(_chunk(source), ASROptions("whisper-1", "ru"))

    request = client.calls[0]
    assert request["model"] == "whisper-1"
    assert request["language"] == "ru"
    assert request["response_format"] == "verbose_json"
    assert request["timestamp_granularities"] == ["word", "segment"]
    assert request["temperature"] == 0
    assert result.segments[0].words[0].start_s == 0
    assert result.language == "ru"
    assert "sk-test" not in repr(adapter)


def test_openai_rejects_oversized_or_incompatible_upload_before_client_call(tmp_path: Path) -> None:
    source = tmp_path / "chunk.flac"
    client = Client(_response())
    adapter = OpenAIASR(
        client,
        api_key="sk-test",
        consent=UploadConsent("openai", True, False),
        max_upload_bytes=4,
    )
    chunk = _chunk(source)

    with pytest.raises(SafeError) as size_error:
        adapter.transcribe(chunk, ASROptions("whisper-1", None))
    assert "size" in size_error.value.render({"sk-test"})
    with pytest.raises(SafeError) as model_error:
        adapter.transcribe(chunk, ASROptions("gpt-4o-transcribe", None))
    assert "word timestamps" in model_error.value.render({"sk-test"})
    assert client.calls == []


def test_openai_rejects_missing_words_and_redacts_provider_error(tmp_path: Path) -> None:
    source = tmp_path / "chunk.flac"
    malformed = OpenAIASR(
        Client({"text": "spoken but no timestamps", "segments": []}),
        api_key="sk-test",
        consent=UploadConsent("openai", True, False),
    )
    with pytest.raises(SafeError) as malformed_error:
        malformed.transcribe(_chunk(source), ASROptions("whisper-1", None))
    assert "word timestamps" in malformed_error.value.render({"sk-test"})

    failing = OpenAIASR(
        Client(RuntimeError("rate limited OPENAI_API_KEY=sk-test")),
        api_key="sk-test",
        consent=UploadConsent("openai", True, False),
    )
    with pytest.raises(SafeError) as provider_error:
        failing.transcribe(_chunk(source), ASROptions("whisper-1", None))
    rendered = provider_error.value.render({"sk-test"})
    assert "sk-test" not in rendered
    assert "retry" in rendered
