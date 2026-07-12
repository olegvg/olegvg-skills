"""ffmpeg/ffprobe media preparation behind a shell-free command boundary."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from .interfaces import CommandRunner
from .models import AudioChunk, AudioMetadata, AudioStream, AudioWindow

_MEAN_VOLUME = re.compile(r"mean_volume:\s*(?P<value>-?(?:\d+(?:\.\d+)?)|-inf)\s*dB", re.I)


@dataclass(frozen=True, slots=True)
class AudioTools:
    ffmpeg: str
    ffprobe: str


def require_audio_tools(which: Callable[[str], str | None]) -> AudioTools:
    ffmpeg = which("ffmpeg")
    ffprobe = which("ffprobe")
    if not ffmpeg:
        raise ValueError("ffmpeg is required for audio preparation")
    if not ffprobe:
        raise ValueError("ffprobe is required for audio inspection")
    return AudioTools(ffmpeg=ffmpeg, ffprobe=ffprobe)


def _run(runner: CommandRunner, argv: tuple[str, ...], *, include_stderr: bool = False) -> str:
    try:
        result = runner(argv, timeout_s=60.0)
    except (OSError, TimeoutError) as exc:
        raise ValueError("audio tool invocation failed") from exc
    if result.returncode != 0:
        raise ValueError("audio tool reported a failure")
    return f"{result.stdout}\n{result.stderr}" if include_stderr else result.stdout


def _positive_float(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"ffprobe {field} is invalid")
    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError(f"ffprobe {field} is invalid") from exc
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"ffprobe {field} is invalid")
    return number


def _positive_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"ffprobe {field} is invalid")
    try:
        number = int(value)
    except ValueError as exc:
        raise ValueError(f"ffprobe {field} is invalid") from exc
    if number <= 0:
        raise ValueError(f"ffprobe {field} is invalid")
    return number


def _nonnegative_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"ffprobe {field} is invalid")
    try:
        number = int(value)
    except ValueError as exc:
        raise ValueError(f"ffprobe {field} is invalid") from exc
    if number < 0:
        raise ValueError(f"ffprobe {field} is invalid")
    return number


def inspect_audio(path: Path, runner: CommandRunner, tools: AudioTools) -> AudioMetadata:
    """Read the first audio stream from strict, machine-readable ffprobe JSON."""
    output = _run(
        runner,
        (
            tools.ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration,format_name,size:stream=index,codec_type,codec_name,sample_rate,channels",
            "-of",
            "json",
            str(path),
        ),
    )
    try:
        payload = cast(object, json.loads(output))
    except json.JSONDecodeError as exc:
        raise ValueError("ffprobe did not return valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("ffprobe JSON is invalid")
    payload_object = cast(dict[str, object], payload)
    raw_format = payload_object.get("format")
    raw_streams = payload_object.get("streams")
    if not isinstance(raw_format, dict) or not isinstance(raw_streams, list):
        raise ValueError("ffprobe JSON is missing format or streams")
    format_object = cast(dict[str, object], raw_format)
    streams_list = cast(list[object], raw_streams)
    format_name = format_object.get("format_name")
    if not isinstance(format_name, str) or not format_name:
        raise ValueError("ffprobe format name is invalid")
    streams: list[AudioStream] = []
    for raw_stream in streams_list:
        if not isinstance(raw_stream, dict):
            continue
        stream_object = cast(dict[str, object], raw_stream)
        if stream_object.get("codec_type") != "audio":
            continue
        codec_name = stream_object.get("codec_name")
        if not isinstance(codec_name, str) or not codec_name:
            raise ValueError("ffprobe audio codec is invalid")
        streams.append(
            AudioStream(
                index=_nonnegative_int(stream_object.get("index"), "stream index"),
                codec_name=codec_name,
                channels=_positive_int(stream_object.get("channels"), "channels"),
                sample_rate_hz=_positive_int(stream_object.get("sample_rate"), "sample rate"),
            )
        )
    if not streams:
        raise ValueError("audio input has no usable audio stream")
    return AudioMetadata(
        duration_s=_positive_float(format_object.get("duration"), "duration"),
        format_name=format_name,
        size_bytes=_positive_int(format_object.get("size"), "size"),
        streams=tuple(streams),
    )


def normalize_for_diarization(
    source: Path, destination: Path, runner: CommandRunner, tools: AudioTools
) -> Path:
    """Produce a private mono 16-kHz PCM WAV and verify the resulting stream."""
    _run(
        runner,
        (
            tools.ffmpeg,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-map",
            "0:a:0",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(destination),
        ),
    )
    metadata = inspect_audio(destination, runner, tools)
    stream = metadata.streams[0]
    if stream.channels != 1 or stream.sample_rate_hz != 16_000 or stream.codec_name != "pcm_s16le":
        raise ValueError("normalized audio is not mono 16-kHz PCM")
    return destination


def _rounded(value: float) -> float:
    return round(value, 6)


def plan_chunks(
    metadata: AudioMetadata, *, max_duration_s: float, overlap_s: float
) -> tuple[AudioWindow, ...]:
    if not math.isfinite(max_duration_s) or max_duration_s <= 0:
        raise ValueError("max chunk duration must be positive")
    if not math.isfinite(overlap_s) or overlap_s < 0 or overlap_s >= max_duration_s:
        raise ValueError("overlap must be non-negative and smaller than chunk duration")
    windows: list[AudioWindow] = []
    start = 0.0
    previous_end = 0.0
    index = 0
    while start < metadata.duration_s:
        end = min(start + max_duration_s, metadata.duration_s)
        if end <= start:
            raise ValueError("chunk planning produced a non-positive interval")
        next_start = end - overlap_s
        windows.append(
            AudioWindow(
                id=f"chunk-{index:04d}",
                start_s=_rounded(start),
                end_s=_rounded(end),
                overlap_before_s=_rounded(0.0 if index == 0 else previous_end - start),
                overlap_after_s=_rounded(0.0 if end >= metadata.duration_s else end - next_start),
            )
        )
        if end >= metadata.duration_s:
            break
        previous_end = end
        start = next_start
        index += 1
    return tuple(windows)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def materialize_chunk(
    source: Path,
    window: AudioWindow,
    destination: Path,
    runner: CommandRunner,
    tools: AudioTools,
) -> AudioChunk:
    duration_s = window.end_s - window.start_s
    if duration_s <= 0:
        raise ValueError("audio chunk interval must be positive")
    _run(
        runner,
        (
            tools.ffmpeg,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{window.start_s:.6f}",
            "-i",
            str(source),
            "-t",
            f"{duration_s:.6f}",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "flac",
            str(destination),
        ),
    )
    if destination.is_symlink() or not destination.is_file() or destination.stat().st_size <= 0:
        raise ValueError("ffmpeg did not create a valid chunk artifact")
    chunk_metadata = inspect_audio(destination, runner, tools)
    if abs(chunk_metadata.duration_s - duration_s) > max(0.1, duration_s * 0.02):
        raise ValueError("materialized chunk duration is outside tolerance")
    return AudioChunk(
        window=window,
        path=destination,
        size_bytes=destination.stat().st_size,
        sha256=_hash_file(destination),
    )


def split_window_for_upload(window: AudioWindow) -> tuple[AudioWindow, AudioWindow]:
    """Bisect an oversized provider-upload interval without creating sub-second files."""
    duration_s = window.end_s - window.start_s
    if duration_s < 2.0:
        raise ValueError("cannot split an oversized audio interval below one second")
    midpoint = _rounded(window.start_s + duration_s / 2)
    return (
        AudioWindow(
            id=f"{window.id}-part-a",
            start_s=window.start_s,
            end_s=midpoint,
            overlap_before_s=window.overlap_before_s,
            overlap_after_s=0.0,
        ),
        AudioWindow(
            id=f"{window.id}-part-b",
            start_s=midpoint,
            end_s=window.end_s,
            overlap_before_s=0.0,
            overlap_after_s=window.overlap_after_s,
        ),
    )


def materialize_upload_chunks(
    source: Path,
    windows: Sequence[AudioWindow],
    *,
    destination_for: Callable[[AudioWindow], Path],
    runner: CommandRunner,
    tools: AudioTools,
    max_upload_bytes: int,
) -> tuple[AudioChunk, ...]:
    """Materialize only sub-ceiling provider uploads, bisecting private artifacts as needed."""
    if max_upload_bytes <= 0:
        raise ValueError("upload byte ceiling must be positive")
    pending = list(windows)
    materialized: list[AudioChunk] = []
    while pending:
        window = pending.pop(0)
        chunk = materialize_chunk(source, window, destination_for(window), runner, tools)
        if chunk.size_bytes < max_upload_bytes:
            materialized.append(chunk)
            continue
        if chunk.path.is_file() and not chunk.path.is_symlink():
            chunk.path.unlink()
        first, second = split_window_for_upload(window)
        pending[0:0] = [first, second]
    return tuple(materialized)


def measure_mean_volume_dbfs(chunk: AudioChunk, runner: CommandRunner, tools: AudioTools) -> float:
    output = _run(
        runner,
        (
            tools.ffmpeg,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "info",
            "-i",
            str(chunk.path),
            "-af",
            "volumedetect",
            "-f",
            "null",
            "-",
        ),
        include_stderr=True,
    )
    match = _MEAN_VOLUME.search(output)
    if match is None:
        raise ValueError("ffmpeg volumedetect did not report mean volume")
    value = match.group("value").lower()
    if value == "-inf":
        return float("-inf")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("ffmpeg mean volume is invalid")
    return float("-inf") if result <= -90.0 else result
