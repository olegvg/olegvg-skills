from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from audio_transcriber.asr_local import FasterWhisperASR, MlxASR
from audio_transcriber.errors import SafeError
from audio_transcriber.models import ASROptions, AudioChunk, AudioWindow, BackendFamily


def _chunk() -> AudioChunk:
    return AudioChunk(
        AudioWindow("chunk-0000", 0, 5, 0, 0), Path("/private/tmp/chunk.flac"), 1, "a" * 64
    )


@dataclass
class FakeWord:
    start: float
    end: float
    word: str
    probability: float | None = None


@dataclass
class FakeSegment:
    start: float
    end: float
    text: str
    words: tuple[FakeWord, ...]
    avg_logprob: float | None = None
    no_speech_prob: float | None = None


def test_mlx_requests_independent_word_timestamps_and_is_lazy() -> None:
    calls: list[dict[str, object]] = []
    loads = 0

    def factory():
        nonlocal loads
        loads += 1

        def transcribe(path: str, **kwargs: object) -> dict[str, object]:
            calls.append({"path": path, **kwargs})
            return {
                "language": "ru",
                "segments": [
                    {
                        "start": 0,
                        "end": 1,
                        "text": "привет",
                        "words": [{"start": 0, "end": 1, "word": "привет", "probability": 0.9}],
                    }
                ],
            }

        return transcribe

    adapter = MlxASR(factory)
    result = adapter.transcribe(_chunk(), ASROptions(model="mlx-model", language="ru", beam_size=5))
    adapter.transcribe(_chunk(), ASROptions(model="mlx-model", language="ru", beam_size=5))

    assert loads == 1
    assert result.language == "ru"
    assert calls[0]["word_timestamps"] is True
    assert calls[0]["condition_on_previous_text"] is False
    assert calls[0]["path_or_hf_repo"] == "mlx-model"
    assert calls[0]["beam_size"] == 5


def test_faster_whisper_uses_approved_cuda_or_cpu_compute_and_exhausts_segments() -> None:
    loads: list[tuple[str, str, str]] = []
    calls: list[dict[str, object]] = []

    class Model:
        def transcribe(self, path: str, **kwargs: object):
            calls.append({"path": path, **kwargs})
            return iter((FakeSegment(0, 1, "hello", (FakeWord(0, 1, "hello", 0.8),)),)), type(
                "Info", (), {"language": "en"}
            )()

    def factory(model: str, device: str, compute_type: str) -> Model:
        loads.append((model, device, compute_type))
        return Model()

    cuda = FasterWhisperASR(factory, BackendFamily.CUDA, cuda_compute_type="float16")
    cpu = FasterWhisperASR(factory, BackendFamily.CPU, cuda_compute_type="float16")
    options = ASROptions(model="local", language="en", beam_size=5)

    assert cuda.transcribe(_chunk(), options).segments[0].words[0].text == "hello"
    cpu.transcribe(_chunk(), options)

    assert loads == [("local", "cuda", "float16"), ("local", "cpu", "int8")]
    assert calls[0]["word_timestamps"] is True
    assert calls[0]["condition_on_previous_text"] is False
    assert calls[0]["beam_size"] == 5
    assert calls[0]["language"] == "en"


def test_local_adapter_rejects_disabled_timestamp_contract_and_redacts_backend_errors() -> None:
    adapter = MlxASR(lambda: (_ for _ in ()).throw(RuntimeError("OPENAI_API_KEY=sk-test")))
    with pytest.raises(SafeError) as raised:
        adapter.transcribe(_chunk(), ASROptions(model="model", language=None))

    assert "sk-test" not in raised.value.render({"sk-test"})
    with pytest.raises(SafeError) as contract_error:
        adapter.transcribe(
            _chunk(),
            ASROptions(model="model", language=None, word_timestamps=False),
        )
    assert "timestamps" in contract_error.value.render(set())
