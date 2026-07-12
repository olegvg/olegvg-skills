from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from audio_transcriber.audio import (
    AudioTools,
    inspect_audio,
    materialize_chunk,
    measure_mean_volume_dbfs,
    normalize_for_diarization,
    plan_chunks,
    require_audio_tools,
    split_window_for_upload,
)
from audio_transcriber.models import AudioMetadata, AudioStream, AudioWindow


class Runner:
    def __init__(self, responses: Mapping[str, subprocess.CompletedProcess[str]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, ...]] = []

    def __call__(
        self,
        argv: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        timeout_s: float = 10.0,
    ) -> subprocess.CompletedProcess[str]:
        del env, timeout_s
        command = tuple(argv)
        self.calls.append(command)
        return self.responses.get(
            command[0], subprocess.CompletedProcess(argv, 1, "", "unavailable")
        )


def _result(
    command: str, stdout: str = "", returncode: int = 0
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess((command,), returncode, stdout, "failed")


def _metadata_json(duration: float = 12.0) -> str:
    return json.dumps(
        {
            "format": {"duration": str(duration), "format_name": "wav", "size": "16000"},
            "streams": [
                {
                    "index": 0,
                    "codec_type": "audio",
                    "codec_name": "pcm_s16le",
                    "sample_rate": "16000",
                    "channels": 1,
                }
            ],
        }
    )


def _tools() -> AudioTools:
    return AudioTools(ffmpeg="ffmpeg", ffprobe="ffprobe")


def test_require_audio_tools_fails_before_backend_use() -> None:
    with pytest.raises(ValueError, match="ffmpeg"):
        require_audio_tools(lambda _: None)
    assert require_audio_tools(lambda name: f"/bin/{name}") == AudioTools(
        ffmpeg="/bin/ffmpeg", ffprobe="/bin/ffprobe"
    )


@pytest.mark.parametrize(
    "payload",
    [
        "not json",
        json.dumps({"format": {}, "streams": []}),
        _metadata_json(0),
        _metadata_json(float("nan")),
    ],
)
def test_inspect_audio_rejects_malformed_or_non_audio_ffprobe(payload: str, tmp_path: Path) -> None:
    source = tmp_path / "recording.wav"
    source.write_bytes(b"audio")
    runner = Runner({"ffprobe": _result("ffprobe", payload)})

    with pytest.raises(ValueError):
        inspect_audio(source, runner, _tools())


def test_inspection_and_normalization_keep_unicode_path_as_one_argv_element(tmp_path: Path) -> None:
    source = tmp_path / "запись с пробелом.wav"
    destination = tmp_path / "normalized.wav"
    source.write_bytes(b"original")
    destination.write_bytes(b"normalized")
    runner = Runner({"ffprobe": _result("ffprobe", _metadata_json()), "ffmpeg": _result("ffmpeg")})

    metadata = inspect_audio(source, runner, _tools())
    normalize_for_diarization(source, destination, runner, _tools())

    assert metadata.duration_s == 12.0
    assert any(str(source) in call for call in runner.calls)
    assert all(
        sum(item == str(source) for item in call) == 1
        for call in runner.calls
        if str(source) in call
    )
    ffmpeg_call = next(call for call in runner.calls if call[0] == "ffmpeg")
    assert ("-ac", "1") == ffmpeg_call[ffmpeg_call.index("-ac") : ffmpeg_call.index("-ac") + 2]
    assert ("-ar", "16000") == ffmpeg_call[ffmpeg_call.index("-ar") : ffmpeg_call.index("-ar") + 2]
    assert source.read_bytes() == b"original"


def test_plan_chunks_is_gap_free_and_bounded() -> None:
    metadata = AudioMetadata(
        duration_s=22.0,
        format_name="wav",
        size_bytes=1,
        streams=(AudioStream(index=0, codec_name="pcm_s16le", channels=1, sample_rate_hz=16_000),),
    )

    chunks = plan_chunks(metadata, max_duration_s=10.0, overlap_s=2.0)

    assert [(chunk.start_s, chunk.end_s) for chunk in chunks] == [
        (0.0, 10.0),
        (8.0, 18.0),
        (16.0, 22.0),
    ]
    assert chunks[1].overlap_before_s == 2.0
    assert chunks[-1].overlap_after_s == 0.0
    with pytest.raises(ValueError, match="smaller"):
        plan_chunks(metadata, max_duration_s=10.0, overlap_s=10.0)


def test_oversized_openai_window_bisects_without_subsecond_children() -> None:
    first, second = split_window_for_upload(AudioWindow("chunk-0000", 0, 10, 0, 2))

    assert (first.start_s, first.end_s, first.id) == (0, 5, "chunk-0000-part-a")
    assert (second.start_s, second.end_s, second.id) == (5, 10, "chunk-0000-part-b")
    with pytest.raises(ValueError, match="one second"):
        split_window_for_upload(AudioWindow("tiny", 0, 1.9, 0, 0))


def test_materialize_chunk_and_parse_volume(tmp_path: Path) -> None:
    source = tmp_path / "normalized.wav"
    source.write_bytes(b"source")
    destination = tmp_path / ".tmp-chunk.flac"
    destination.write_bytes(b"flac")
    window = AudioWindow("chunk-0000", 0.0, 12.0, 0.0, 0.0)
    runner = Runner(
        {
            "ffmpeg": _result("ffmpeg", "[Parsed_volumedetect] mean_volume: -55.2 dB\n"),
            "ffprobe": _result("ffprobe", _metadata_json()),
        }
    )

    chunk = materialize_chunk(source, window, destination, runner, _tools())

    assert chunk.path == destination
    assert chunk.size_bytes == 4
    assert measure_mean_volume_dbfs(chunk, runner, _tools()) == -55.2
    assert any("-ss" in call and "-t" in call for call in runner.calls)


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg and ffprobe are host prerequisites",
)
def test_generated_wav_can_be_inspected_normalized_and_chunked(
    generated_wav: tuple[Path, Path], tmp_path: Path
) -> None:
    tone, silence = generated_wav

    def runner(
        argv: Sequence[str], *, env: Mapping[str, str] | None = None, timeout_s: float = 10.0
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            argv, check=False, capture_output=True, text=True, env=env, timeout=timeout_s
        )

    tools = require_audio_tools(shutil.which)
    metadata = inspect_audio(tone, runner, tools)
    normalized = tmp_path / "normalized.wav"
    normalize_for_diarization(tone, normalized, runner, tools)
    normalized_metadata = inspect_audio(normalized, runner, tools)
    chunk = materialize_chunk(
        normalized,
        plan_chunks(metadata, max_duration_s=10, overlap_s=1)[0],
        tmp_path / "chunk.flac",
        runner,
        tools,
    )

    assert normalized_metadata.streams[0].sample_rate_hz == 16_000
    assert normalized_metadata.streams[0].channels == 1
    assert chunk.size_bytes > 0
    assert measure_mean_volume_dbfs(chunk, runner, tools) > -50
    silent_chunk = materialize_chunk(
        silence,
        AudioWindow("silent", 0, 1, 0, 0),
        tmp_path / "silent.flac",
        runner,
        tools,
    )
    assert measure_mean_volume_dbfs(silent_chunk, runner, tools) == float("-inf")
