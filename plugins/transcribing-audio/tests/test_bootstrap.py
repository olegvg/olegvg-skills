import json
import os
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

import audio_transcriber.bootstrap as bootstrap

from audio_transcriber.bootstrap import (
    CapabilityReport,
    RuntimeHandle,
    SystemInfo,
    choose_backend,
    ensure_runtime,
    mark_runtime_component_unhealthy,
    probe_capabilities,
    reexec_after_component_failure,
    validate_input_path,
)
from audio_transcriber.models import BackendFamily, ComputeDevice
from audio_transcriber.models import RuntimeComponent
from audio_transcriber.errors import SafeError


class RecordingRunner:
    def __init__(
        self, responses: Mapping[tuple[str, ...], subprocess.CompletedProcess[str]]
    ) -> None:
        self.responses = responses
        self.calls: list[tuple[tuple[str, ...], Mapping[str, str] | None]] = []

    def __call__(
        self,
        argv: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        timeout_s: float = 10.0,
    ) -> subprocess.CompletedProcess[str]:
        key = tuple(argv)
        self.calls.append((key, env))
        response = self.responses.get(key)
        if response is None:
            return subprocess.CompletedProcess(argv, 1, "", "unavailable")
        return response


def _result(
    argv: Sequence[str], stdout: str = "", returncode: int = 0
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(argv, returncode, stdout, "")


def _system(os_name: str, architecture: str) -> SystemInfo:
    return SystemInfo(
        os_name=os_name,
        architecture=architecture,
        python_major=3,
        python_minor=13,
        os_version="14.0" if os_name == "Darwin" else "",
    )


def test_mlx_precedes_cuda_on_verified_apple_silicon() -> None:
    runner = RecordingRunner(
        {
            ("system_profiler", "SPDisplaysDataType", "-json"): _result(
                ("system_profiler", "SPDisplaysDataType", "-json"),
                json.dumps({"SPDisplaysDataType": [{"spdisplays_metal": "Metal 3"}]}),
            )
        }
    )

    report = probe_capabilities(runner, _system("Darwin", "arm64"))

    assert choose_backend(report) is BackendFamily.MLX
    assert report.compute_device is ComputeDevice.MPS
    assert all(call[0][0] != "nvidia-smi" for call in runner.calls)


def test_healthy_nvidia_runtime_selects_cuda() -> None:
    runner = RecordingRunner(
        {
            (
                "nvidia-smi",
                "--query-gpu=driver_version,compute_cap",
                "--format=csv,noheader",
            ): _result(
                ("nvidia-smi", "--query-gpu=driver_version,compute_cap", "--format=csv,noheader"),
                "555.42, 8.9\n",
            )
        }
    )

    report = probe_capabilities(runner, _system("Linux", "x86_64"))

    assert report.selected_backend is BackendFamily.CUDA
    assert report.compute_device is ComputeDevice.CUDA


def test_cpu_fallback_records_a_safe_reason() -> None:
    report = probe_capabilities(RecordingRunner({}), _system("Darwin", "x86_64"))

    assert report.selected_backend is BackendFamily.CPU
    assert report.compute_device is ComputeDevice.CPU
    assert report.fallback_reasons


def test_timeout_or_invalid_cuda_output_falls_back_to_cpu() -> None:
    runner = RecordingRunner(
        {
            (
                "nvidia-smi",
                "--query-gpu=driver_version,compute_cap",
                "--format=csv,noheader",
            ): _result(
                ("nvidia-smi", "--query-gpu=driver_version,compute_cap", "--format=csv,noheader"),
                "not-a-cuda-row",
            )
        }
    )

    report = probe_capabilities(runner, _system("Linux", "x86_64"))

    assert report.selected_backend is BackendFamily.CPU


def test_capability_report_round_trips_only_safe_platform_facts() -> None:
    report = CapabilityReport(
        system=_system("Darwin", "arm64"),
        mlx_available=True,
        cuda_available=False,
        selected_backend=BackendFamily.MLX,
        compute_device=ComputeDevice.MPS,
        fallback_reasons=("CUDA is not applicable",),
    )

    assert CapabilityReport.from_dict(report.to_dict()) == report
    with pytest.raises(ValueError, match="fallback_reasons"):
        CapabilityReport.from_dict({**report.to_dict(), "fallback_reasons": [1]})


def test_probes_never_inherit_ambient_provider_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-live-secret")
    monkeypatch.setenv("HF_TOKEN", "hf-secret")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "aws-secret")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "langfuse-secret")
    monkeypatch.setenv("HF_HOME", "/safe/persistent-model-cache")
    runner = RecordingRunner(
        {
            ("system_profiler", "SPDisplaysDataType", "-json"): _result(
                ("system_profiler", "SPDisplaysDataType", "-json"),
                json.dumps({"SPDisplaysDataType": [{"spdisplays_metal": "Metal 3"}]}),
            )
        }
    )

    probe_capabilities(runner, _system("Darwin", "arm64"))

    assert runner.calls
    assert all(
        environment is not None
        and "OPENAI_API_KEY" not in environment
        and "HF_TOKEN" not in environment
        and "AWS_SECRET_ACCESS_KEY" not in environment
        and "LANGFUSE_SECRET_KEY" not in environment
        and environment["HF_HOME"] == "/safe/persistent-model-cache"
        for _, environment in runner.calls
    )


def test_validate_input_path_rejects_symlinks(tmp_path: Path) -> None:
    recording = tmp_path / "recording.wav"
    recording.write_bytes(b"audio")
    link = tmp_path / "recording-link.wav"
    link.symlink_to(recording)

    assert validate_input_path(recording) == recording
    with pytest.raises(ValueError, match="symlink"):
        validate_input_path(link)


def test_unsafe_input_is_rejected_before_runtime_provisioning(tmp_path: Path) -> None:
    root = _plugin_root(tmp_path)
    recording = tmp_path / "recording.wav"
    recording.write_bytes(b"audio")
    link = tmp_path / "recording-link.wav"
    link.symlink_to(recording)
    runner = _runtime_runner(root)

    with pytest.raises(ValueError, match="symlink"):
        ensure_runtime(
            root,
            reprobe=False,
            runner=runner,
            system=_system("Darwin", "arm64"),
            runtime_root=tmp_path / "state",
            input_path=link,
        )

    assert not any(call[:2] == ("uv", "sync") for call, _ in runner.calls)


def test_missing_host_prerequisite_prevents_venv_provisioning(tmp_path: Path) -> None:
    root = _plugin_root(tmp_path)
    runner = RecordingRunner({})

    with pytest.raises(SafeError):
        ensure_runtime(
            root,
            reprobe=False,
            runner=runner,
            system=_system("Darwin", "arm64"),
            runtime_root=tmp_path / "state",
        )

    assert not any(call[:2] == ("uv", "sync") for call, _ in runner.calls)


def test_private_runtime_symlink_is_rejected_before_venv_provisioning(tmp_path: Path) -> None:
    root = _plugin_root(tmp_path)
    target = tmp_path / "target"
    target.mkdir()
    runtime_root = tmp_path / "state"
    runtime_root.symlink_to(target, target_is_directory=True)
    runner = _runtime_runner(root)

    with pytest.raises(SafeError):
        ensure_runtime(
            root,
            reprobe=False,
            runner=runner,
            system=_system("Darwin", "arm64"),
            runtime_root=runtime_root,
        )

    assert runner.calls == []


def test_cli_module_renders_help_when_reexecuted() -> None:
    scripts_root = Path(__file__).resolve().parents[1] / "scripts"
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(scripts_root)

    completed = subprocess.run(
        [sys.executable, "-P", "-m", "audio_transcriber.cli", "--help"],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )

    assert completed.returncode == 0
    assert "Transcribe audio" in completed.stdout


def _plugin_root(tmp_path: Path) -> Path:
    root = tmp_path / "transcribing-audio"
    root.mkdir()
    (root / "uv.lock").write_text("lock-v1")
    python = root / ".venv" / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.write_text("#!/bin/sh\n")
    python.chmod(0o700)
    return root


def _runtime_runner(root: Path) -> RecordingRunner:
    python = root / ".venv" / "bin" / "python"
    return RecordingRunner(
        {
            ("uv", "--version"): _result(("uv", "--version"), "uv 0.11"),
            ("ffmpeg", "-version"): _result(("ffmpeg", "-version"), "ffmpeg"),
            ("ffprobe", "-version"): _result(("ffprobe", "-version"), "ffprobe"),
            ("system_profiler", "SPDisplaysDataType", "-json"): _result(
                ("system_profiler", "SPDisplaysDataType", "-json"),
                json.dumps({"SPDisplaysDataType": [{"spdisplays_metal": "Metal 3"}]}),
            ),
            (
                "uv",
                "sync",
                "--project",
                str(root),
                "--frozen",
                "--no-dev",
                "--all-extras",
                "--python",
                "3.13",
            ): _result(("uv", "sync")),
            (str(python), "-P", "-c", "import audio_transcriber"): _result(
                (str(python), "-P", "-c", "import audio_transcriber")
            ),
        }
    )


def test_cached_runtime_skips_probe_and_sync_but_reprobe_reuses_same_venv(tmp_path: Path) -> None:
    root = _plugin_root(tmp_path)
    runner = _runtime_runner(root)
    runtime_root = tmp_path / "state"

    first = ensure_runtime(
        root,
        reprobe=False,
        runner=runner,
        system=_system("Darwin", "arm64"),
        runtime_root=runtime_root,
    )
    assert first.python == root / ".venv" / "bin" / "python"
    sync_calls = [call for call, _ in runner.calls if call[:2] == ("uv", "sync")]
    assert len(sync_calls) == 1
    sync_environment = next(env for call, env in runner.calls if call[:2] == ("uv", "sync"))
    assert sync_environment is not None
    assert sync_environment["UV_PROJECT_ENVIRONMENT"] == str(root / ".venv")

    runner.calls.clear()
    second = ensure_runtime(
        root,
        reprobe=False,
        runner=runner,
        system=_system("Darwin", "arm64"),
        runtime_root=runtime_root,
    )
    assert second == first
    assert runner.calls == []

    reprobed = ensure_runtime(
        root,
        reprobe=True,
        runner=runner,
        system=_system("Darwin", "arm64"),
        runtime_root=runtime_root,
    )
    assert reprobed.python == first.python
    assert any(call[0] == "system_profiler" for call, _ in runner.calls)
    assert not any(call[:2] == ("uv", "sync") for call, _ in runner.calls)
    assert os.stat(root / ".venv").st_mode & 0o777 == 0o700


def test_cached_runtime_rejects_a_venv_symlink(tmp_path: Path) -> None:
    root = _plugin_root(tmp_path)
    runner = _runtime_runner(root)
    runtime_root = tmp_path / "state"
    ensure_runtime(
        root,
        reprobe=False,
        runner=runner,
        system=_system("Darwin", "arm64"),
        runtime_root=runtime_root,
    )
    moved_venv = tmp_path / "moved-venv"
    (root / ".venv").rename(moved_venv)
    (root / ".venv").symlink_to(moved_venv, target_is_directory=True)

    with pytest.raises(SafeError) as captured:
        ensure_runtime(
            root,
            reprobe=False,
            runner=runner,
            system=_system("Darwin", "arm64"),
            runtime_root=runtime_root,
        )

    assert "unsafe" in captured.value.render(set())

    shutil.rmtree(moved_venv)


def test_unhealthy_component_persists_only_safe_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_root = tmp_path / "state"
    monkeypatch.setattr(bootstrap, "_runtime_root", lambda: runtime_root)
    runtime = RuntimeHandle(
        runtime_fingerprint="runtime",
        base_fingerprint="base",
        python=Path("/safe/python"),
        backend=BackendFamily.MLX,
        compute_device=ComputeDevice.MPS,
        state_path=runtime_root / "state.json",
        plugin_root=tmp_path,
        recovery_attempt=False,
    )

    ticket = mark_runtime_component_unhealthy(
        runtime,
        RuntimeComponent.ASR_MLX,
        "provider error sk-live-secret",
    )

    persisted = (runtime_root / "runtime" / "unhealthy.json").read_text()
    assert "sk-live-secret" not in persisted
    assert "timestamp" in persisted
    assert "sk-live-secret" not in ticket.reason


def test_recovery_honors_exclusions_and_reprobe_clears_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _plugin_root(tmp_path)
    runtime_root = tmp_path / "state"
    monkeypatch.setattr(bootstrap, "_runtime_root", lambda: runtime_root)
    runner = _runtime_runner(root)
    initial = ensure_runtime(
        root,
        reprobe=False,
        runner=runner,
        system=_system("Darwin", "arm64"),
        runtime_root=runtime_root,
    )
    mark_runtime_component_unhealthy(initial, RuntimeComponent.ASR_MLX, "failed")
    monkeypatch.setenv("TRANSCRIBING_AUDIO_RUNTIME_RECOVERY_ATTEMPT", "1")

    recovered = ensure_runtime(
        root,
        reprobe=False,
        runner=runner,
        system=_system("Darwin", "arm64"),
        runtime_root=runtime_root,
    )

    assert recovered.recovery_attempt
    assert recovered.backend is BackendFamily.CPU

    reprobed = ensure_runtime(
        root,
        reprobe=True,
        runner=runner,
        system=_system("Darwin", "arm64"),
        runtime_root=runtime_root,
    )

    assert reprobed.backend is BackendFamily.MLX
    assert not (runtime_root / "runtime" / "unhealthy.json").exists()


def test_recovery_reexecs_once_and_stops_after_a_second_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_root = tmp_path / "state"
    monkeypatch.setattr(bootstrap, "_runtime_root", lambda: runtime_root)
    runtime = RuntimeHandle(
        runtime_fingerprint="runtime",
        base_fingerprint="base",
        python=Path("/safe/python"),
        backend=BackendFamily.MLX,
        compute_device=ComputeDevice.MPS,
        state_path=runtime_root / "state.json",
        plugin_root=tmp_path,
        recovery_attempt=False,
    )
    invoked: list[tuple[Path, list[str], Mapping[str, str]]] = []

    def fake_execve(path: Path, argv: list[str], env: Mapping[str, str]) -> None:
        invoked.append((path, argv, env))
        raise RuntimeError("reexec")

    monkeypatch.setattr(bootstrap.os, "execve", fake_execve)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-live-secret")

    with pytest.raises(RuntimeError, match="reexec"):
        reexec_after_component_failure(runtime, RuntimeComponent.ASR_MLX, "failure", ["audio.m4a"])

    assert invoked[0][1] == [
        "/safe/python",
        str(tmp_path / "scripts" / "transcribe_audio.py"),
        "audio.m4a",
    ]
    assert invoked[0][2]["TRANSCRIBING_AUDIO_RUNTIME_RECOVERY_ATTEMPT"] == "1"
    assert "OPENAI_API_KEY" not in invoked[0][2]

    repeated = RuntimeHandle(
        runtime_fingerprint=runtime.runtime_fingerprint,
        base_fingerprint=runtime.base_fingerprint,
        python=runtime.python,
        backend=runtime.backend,
        compute_device=runtime.compute_device,
        state_path=runtime.state_path,
        plugin_root=runtime.plugin_root,
        recovery_attempt=True,
    )
    with pytest.raises(SafeError):
        reexec_after_component_failure(repeated, RuntimeComponent.ASR_MLX, "failure", ["audio.m4a"])
