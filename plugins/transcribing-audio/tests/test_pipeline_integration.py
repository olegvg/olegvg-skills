from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from audio_transcriber.config import ConfigOverrides, ResolvedConfig, resolve_config
from audio_transcriber.models import (
    ASRChunkResult,
    ASROptions,
    AsrSegment,
    AudioChunk,
    BackendFamily,
    ComputeDevice,
    DiarizationTurn,
    Mode,
    SpeakerCount,
    Word,
)
from audio_transcriber.pipeline import PipelineDependencies, PipelineRunner, publish_outputs
from audio_transcriber.bootstrap import RuntimeHandle


class _Runner:
    def __init__(self) -> None:
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
        if command[0] == "ffprobe":
            payload = {
                "format": {"duration": "2", "format_name": "wav", "size": "5"},
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
            return subprocess.CompletedProcess(command, 0, json.dumps(payload), "")
        if command[0] == "ffmpeg":
            if "volumedetect" in command:
                return subprocess.CompletedProcess(command, 0, "", "mean_volume: -20.0 dB")
            Path(command[-1]).parent.mkdir(parents=True, exist_ok=True)
            Path(command[-1]).write_bytes(b"audio")
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(command, 1, "", "unexpected command")


class _ASR:
    def __init__(self) -> None:
        self.transcribe_calls = 0
        self.health_checks = 0

    def health_check(self, model: str) -> None:
        assert model
        self.health_checks += 1

    def transcribe(self, chunk: AudioChunk, options: ASROptions) -> ASRChunkResult:
        self.transcribe_calls += 1
        words = (
            Word(0.0, 0.4, "Привет", 0.9, chunk.window.id),
            Word(0.5, 0.9, "world", 0.9, chunk.window.id),
        )
        return ASRChunkResult(
            chunk,
            "fake-local",
            options.model,
            "ru",
            (AsrSegment(0.0, 0.9, "Привет world", words, None, None),),
        )


class _Diarizer:
    def __init__(self, duration_s: float = 2.0) -> None:
        self.calls = 0
        self.health_checks = 0
        self._duration_s = duration_s

    def health_check(self) -> None:
        self.health_checks += 1

    def diarize(self, audio_path: Path, speakers: SpeakerCount) -> tuple[DiarizationTurn, ...]:
        assert audio_path.is_file()
        del speakers
        self.calls += 1
        return (DiarizationTurn(0.0, self._duration_s, "SPEAKER_00"),)


def _runtime(root: Path) -> RuntimeHandle:
    return RuntimeHandle(
        runtime_fingerprint="a" * 64,
        base_fingerprint="b" * 64,
        python=Path("python"),
        backend=BackendFamily.CPU,
        compute_device=ComputeDevice.CPU,
        state_path=root / "runtime.json",
        plugin_root=root,
        recovery_attempt=False,
    )


def test_local_pipeline_reuses_valid_stages_and_rebuilds_corrupt_descendants(
    tmp_path: Path,
) -> None:
    source = tmp_path / "recording.wav"
    source.write_bytes(b"input")
    (tmp_path / ".env").write_text("HF_TOKEN=hf-test\n")
    config = resolve_config(
        ConfigOverrides(input_path=source, mode=Mode.LOCAL, output_dir=tmp_path / "out"), tmp_path
    )
    runner = _Runner()
    asr = _ASR()
    diarizer = _Diarizer()
    dependencies = PipelineDependencies(
        command_runner=runner,
        which=lambda name: name,
        asr_factory=lambda _config, _runtime, _consent: asr,
        diarizer_factory=lambda _config, _runtime, _duration: diarizer,
        clock=lambda: datetime.now(UTC),
        publisher=publish_outputs,
    )
    pipeline = PipelineRunner(_runtime(tmp_path), dependencies, state_root=tmp_path / "runtime")

    first = pipeline.run(config)
    assert first.json.is_file() and first.txt.is_file()
    assert asr.transcribe_calls == 1
    assert diarizer.calls == 1

    second = pipeline.run(config)
    assert second == first
    assert asr.transcribe_calls == 1
    assert diarizer.calls == 1

    state = next((tmp_path / "runtime" / "runs").iterdir())
    (state / "stages" / "04-diarize" / "diarization.json").write_text("{}")
    pipeline.run(config)

    assert asr.transcribe_calls == 1
    assert diarizer.calls == 2


def test_local_generated_wav_pipeline_succeeds_offline(
    tmp_path: Path, generated_wav: tuple[Path, Path]
) -> None:
    source, _ = generated_wav
    (tmp_path / ".env").write_text("HF_TOKEN=hf-test\n")
    config = resolve_config(
        ConfigOverrides(input_path=source, mode=Mode.LOCAL, output_dir=tmp_path / "out"), tmp_path
    )
    asr = _ASR()
    diarizers: list[_Diarizer] = []

    def runner(
        argv: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        timeout_s: float = 10.0,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            env=env,
            timeout=timeout_s,
        )

    def diarizer_factory(
        _config: ResolvedConfig, _runtime: RuntimeHandle, duration_s: float
    ) -> _Diarizer:
        diarizer = _Diarizer(duration_s)
        diarizers.append(diarizer)
        return diarizer

    pipeline = PipelineRunner(
        _runtime(tmp_path),
        PipelineDependencies(
            command_runner=runner,
            which=shutil.which,
            asr_factory=lambda _config, _runtime, _consent: asr,
            diarizer_factory=diarizer_factory,
            clock=lambda: datetime.now(UTC),
            publisher=publish_outputs,
        ),
        state_root=tmp_path / "runtime",
    )

    outputs = pipeline.run(config)

    assert outputs.json.is_file() and outputs.txt.is_file()
    assert asr.transcribe_calls == 1
    assert diarizers[0].calls == 1
