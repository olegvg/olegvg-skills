"""Stdlib-only runtime probing, caching, and re-execution."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import platform
import stat
import subprocess
import sys
import tempfile
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn, cast

from .constants import (
    REPROBE_FLAG,
    RUNTIME_BOOTSTRAPPED_ENV,
    RUNTIME_RECOVERY_ATTEMPT_ENV,
    RUNTIME_ROOT_NAME,
    RUNTIME_VERSION,
    STATE_SCHEMA_VERSION,
    VENV_DIRECTORY_NAME,
    VENV_STAMP_FILENAME,
)
from .errors import SafeError
from .interfaces import CommandRunner
from .models import BackendFamily, ComputeDevice, RuntimeComponent, StageName

_MAX_PROBE_OUTPUT = 4_096
_APPROVED_PYTHON_MAJOR = 3
_APPROVED_PYTHON_MINOR = 13
_SAFE_ENVIRONMENT_NAMES = frozenset(
    {
        "DYLD_LIBRARY_PATH",
        "HF_HOME",
        "HOME",
        "HUGGINGFACE_HUB_CACHE",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "LD_LIBRARY_PATH",
        "MLX_CACHE_PATH",
        "MPLCONFIGDIR",
        "PATH",
        "SSL_CERT_DIR",
        "SSL_CERT_FILE",
        "TEMP",
        "TMP",
        "TMPDIR",
        "TORCH_HOME",
        "TRANSFORMERS_CACHE",
        "UV_CACHE_DIR",
    }
)


@dataclass(frozen=True, slots=True)
class SystemInfo:
    os_name: str
    architecture: str
    python_major: int
    python_minor: int
    os_version: str = ""


@dataclass(frozen=True, slots=True)
class CapabilityReport:
    system: SystemInfo
    mlx_available: bool
    cuda_available: bool
    selected_backend: BackendFamily
    compute_device: ComputeDevice
    fallback_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "system": {
                "os_name": self.system.os_name,
                "architecture": self.system.architecture,
                "python_major": self.system.python_major,
                "python_minor": self.system.python_minor,
                "os_version": self.system.os_version,
            },
            "mlx_available": self.mlx_available,
            "cuda_available": self.cuda_available,
            "selected_backend": self.selected_backend.value,
            "compute_device": self.compute_device.value,
            "fallback_reasons": list(self.fallback_reasons),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> CapabilityReport:
        system_value = payload.get("system")
        if not isinstance(system_value, dict):
            raise ValueError("capability system is invalid")
        raw_system = cast(dict[object, object], system_value)
        if not all(isinstance(key, str) for key in raw_system):
            raise ValueError("capability system is invalid")
        system_payload = cast(dict[str, object], system_value)
        os_name = _required_string(system_payload, "os_name")
        architecture = _required_string(system_payload, "architecture")
        python_major = _required_int(system_payload, "python_major")
        python_minor = _required_int(system_payload, "python_minor")
        os_version_value = system_payload.get("os_version")
        if not isinstance(os_version_value, str):
            raise ValueError("os_version is invalid")
        os_version = os_version_value
        mlx_available = _required_bool(payload, "mlx_available")
        cuda_available = _required_bool(payload, "cuda_available")
        selected_backend = BackendFamily(_required_string(payload, "selected_backend"))
        compute_device = ComputeDevice(_required_string(payload, "compute_device"))
        reasons_value = payload.get("fallback_reasons")
        if not isinstance(reasons_value, list):
            raise ValueError("fallback_reasons is invalid")
        reasons: list[str] = []
        for item in cast(list[object], reasons_value):
            if not isinstance(item, str):
                raise ValueError("fallback_reasons is invalid")
            reasons.append(item)
        return cls(
            system=SystemInfo(
                os_name=os_name,
                architecture=architecture,
                python_major=python_major,
                python_minor=python_minor,
                os_version=os_version,
            ),
            mlx_available=mlx_available,
            cuda_available=cuda_available,
            selected_backend=selected_backend,
            compute_device=compute_device,
            fallback_reasons=tuple(reasons),
        )


@dataclass(frozen=True, slots=True)
class RuntimeHandle:
    runtime_fingerprint: str
    base_fingerprint: str
    python: Path
    backend: BackendFamily
    compute_device: ComputeDevice
    state_path: Path
    plugin_root: Path
    recovery_attempt: bool


@dataclass(frozen=True, slots=True)
class RecoveryTicket:
    component: RuntimeComponent
    reason: str
    recovery_attempt: bool


def _required_string(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} is invalid")
    return value


def _required_int(payload: Mapping[str, object], field: str) -> int:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} is invalid")
    return value


def _required_bool(payload: Mapping[str, object], field: str) -> bool:
    value = payload.get(field)
    if not isinstance(value, bool):
        raise ValueError(f"{field} is invalid")
    return value


def _current_system() -> SystemInfo:
    return SystemInfo(
        os_name=platform.system(),
        architecture=platform.machine().lower(),
        python_major=_APPROVED_PYTHON_MAJOR,
        python_minor=_APPROVED_PYTHON_MINOR,
        os_version=platform.mac_ver()[0] if platform.system() == "Darwin" else platform.release(),
    )


def _sanitized_environment() -> dict[str, str]:
    return {key: value for key, value in os.environ.items() if key in _SAFE_ENVIRONMENT_NAMES}


def _default_runner(
    argv: Sequence[str], *, env: Mapping[str, str] | None = None, timeout_s: float = 10.0
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(argv),
        check=False,
        shell=False,
        capture_output=True,
        text=True,
        timeout=timeout_s,
        env=dict(env) if env is not None else None,
    )


def _probe_output(runner: CommandRunner, argv: Sequence[str]) -> tuple[bool, str]:
    try:
        result = runner(argv, env=_sanitized_environment(), timeout_s=10.0)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False, ""
    if result.returncode != 0:
        return False, ""
    return True, result.stdout[:_MAX_PROBE_OUTPUT]


def _has_metal_evidence(output: str) -> bool:
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return False
    return "metal" in json.dumps(payload, sort_keys=True).lower()


def _has_cuda_evidence(output: str) -> bool:
    for row in output.splitlines():
        columns = [column.strip() for column in row.split(",")]
        if len(columns) != 2:
            continue
        if (
            columns[0]
            and columns[1]
            and all(character.isdigit() or character == "." for character in columns[1])
        ):
            return True
    return False


def _supports_mlx(system: SystemInfo) -> bool:
    if system.os_name != "Darwin" or system.architecture not in {"arm64", "aarch64"}:
        return False
    try:
        return int(system.os_version.split(".", maxsplit=1)[0]) >= 14
    except (IndexError, ValueError):
        return False


def probe_capabilities(
    runner: CommandRunner,
    system: SystemInfo,
    excluded: frozenset[RuntimeComponent] = frozenset(),
) -> CapabilityReport:
    """Probe MLX, then CUDA, and select the deterministic safe fallback."""
    reasons: list[str] = []
    mlx_available = False
    cuda_available = False

    is_apple_silicon = system.os_name == "Darwin" and system.architecture in {"arm64", "aarch64"}
    if _supports_mlx(system):
        succeeded, output = _probe_output(
            runner, ("system_profiler", "SPDisplaysDataType", "-json")
        )
        mlx_available = succeeded and _has_metal_evidence(output)
        if not mlx_available:
            reasons.append("Metal evidence was unavailable")
    elif is_apple_silicon:
        reasons.append("MLX requires macOS 14 or later")
    else:
        reasons.append("MLX requires macOS on Apple Silicon")

    if mlx_available and RuntimeComponent.ASR_MLX not in excluded:
        compute_device = (
            ComputeDevice.MPS
            if RuntimeComponent.DIARIZATION_MPS not in excluded
            else ComputeDevice.CPU
        )
        if compute_device is ComputeDevice.CPU:
            reasons.append("MPS diarization was excluded after a previous failure")
        return CapabilityReport(
            system=system,
            mlx_available=True,
            cuda_available=False,
            selected_backend=BackendFamily.MLX,
            compute_device=compute_device,
            fallback_reasons=tuple(reasons),
        )
    if mlx_available:
        reasons.append("MLX ASR was excluded after a previous failure")

    if system.os_name == "Linux":
        succeeded, output = _probe_output(
            runner,
            ("nvidia-smi", "--query-gpu=driver_version,compute_cap", "--format=csv,noheader"),
        )
        cuda_available = succeeded and _has_cuda_evidence(output)
        if not cuda_available:
            reasons.append("a healthy NVIDIA CUDA runtime was unavailable")
    else:
        reasons.append("CUDA probing is supported only on Linux in version 1")

    if cuda_available and RuntimeComponent.ASR_CUDA not in excluded:
        compute_device = (
            ComputeDevice.CUDA
            if RuntimeComponent.DIARIZATION_CUDA not in excluded
            else ComputeDevice.CPU
        )
        if compute_device is ComputeDevice.CPU:
            reasons.append("CUDA diarization was excluded after a previous failure")
        return CapabilityReport(
            system=system,
            mlx_available=mlx_available,
            cuda_available=True,
            selected_backend=BackendFamily.CUDA,
            compute_device=compute_device,
            fallback_reasons=tuple(reasons),
        )
    if cuda_available:
        reasons.append("CUDA ASR was excluded after a previous failure")

    return CapabilityReport(
        system=system,
        mlx_available=mlx_available,
        cuda_available=cuda_available,
        selected_backend=BackendFamily.CPU,
        compute_device=ComputeDevice.CPU,
        fallback_reasons=tuple(reasons),
    )


def choose_backend(report: CapabilityReport) -> BackendFamily:
    return report.selected_backend


def validate_input_path(input_path: Path) -> Path:
    """Reject unsafe paths before a future run can create expensive state."""
    if any(character in str(input_path) for character in ("\n", "\r", "\t", "\x00")):
        raise ValueError("input path contains control characters")
    try:
        details = input_path.lstat()
    except FileNotFoundError as error:
        raise ValueError(f"input file does not exist: {input_path}") from error
    if stat.S_ISLNK(details.st_mode):
        raise ValueError("input path must not be a symlink")
    if not stat.S_ISREG(details.st_mode) or not os.access(input_path, os.R_OK):
        raise ValueError("input path must be a readable regular file")
    return input_path


def _lock_digest(plugin_root: Path) -> str:
    lock_path = plugin_root / "uv.lock"
    if not lock_path.is_file():
        raise SafeError(stage=StageName.CONFIGURE, message="plugin uv.lock is missing")
    return hashlib.sha256(lock_path.read_bytes()).hexdigest()


def _base_fingerprint(lock_digest: str, system: SystemInfo) -> str:
    payload = {
        "runtime_version": RUNTIME_VERSION,
        "lock_digest": lock_digest,
        "os": system.os_name,
        "architecture": system.architecture,
        "os_version": system.os_version,
        "python": [system.python_major, system.python_minor],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _runtime_fingerprint(base_fingerprint: str, report: CapabilityReport) -> str:
    payload = {
        "base": base_fingerprint,
        "backend": report.selected_backend.value,
        "compute_device": report.compute_device.value,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _runtime_root() -> Path:
    return Path("/tmp") / f"{RUNTIME_ROOT_NAME}-{os.getuid()}"


def _secure_private_directory(path: Path) -> None:
    if path.exists() or path.is_symlink():
        details = path.lstat()
        if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode):
            raise SafeError(stage=StageName.CONFIGURE, message="runtime root is unsafe")
        if details.st_uid != os.getuid():
            raise SafeError(
                stage=StageName.CONFIGURE, message="runtime root is not owned by the current user"
            )
    else:
        path.mkdir(parents=True, mode=0o700)
    os.chmod(path, 0o700)


def _secure_child_directory(parent: Path, name: str) -> Path:
    _secure_private_directory(parent)
    child = parent / name
    if child.exists() or child.is_symlink():
        details = child.lstat()
        if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode):
            raise SafeError(stage=StageName.CONFIGURE, message="runtime directory is unsafe")
        if details.st_uid != os.getuid():
            raise SafeError(
                stage=StageName.CONFIGURE,
                message="runtime directory is not owned by the current user",
            )
    else:
        child.mkdir(mode=0o700)
    os.chmod(child, 0o700)
    return child


def _runtime_directory(runtime_root: Path) -> Path:
    return _secure_child_directory(runtime_root, "runtime")


def _secure_venv_path(venv_path: Path) -> None:
    if not (venv_path.exists() or venv_path.is_symlink()):
        return
    details = venv_path.lstat()
    if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode):
        raise SafeError(stage=StageName.CONFIGURE, message="plugin virtual environment is unsafe")
    if details.st_uid != os.getuid():
        raise SafeError(
            stage=StageName.CONFIGURE,
            message="plugin virtual environment is not owned by the current user",
        )
    os.chmod(venv_path, 0o700)


def _venv_python(venv_path: Path) -> tuple[Path, Path] | None:
    bin_path = venv_path / "bin"
    if not (bin_path.exists() or bin_path.is_symlink()):
        return None
    bin_details = bin_path.lstat()
    if stat.S_ISLNK(bin_details.st_mode) or not stat.S_ISDIR(bin_details.st_mode):
        raise SafeError(stage=StageName.CONFIGURE, message="plugin virtual environment is unsafe")
    if bin_details.st_uid != os.getuid():
        raise SafeError(
            stage=StageName.CONFIGURE,
            message="plugin virtual environment is not owned by the current user",
        )
    python = bin_path / "python"
    if not (python.exists() or python.is_symlink()) or not os.access(python, os.X_OK):
        return None
    try:
        target = python.resolve(strict=True)
    except OSError as error:
        raise SafeError(
            stage=StageName.CONFIGURE, message="plugin Python executable is unsafe"
        ) from error
    target_details = target.stat()
    if not stat.S_ISREG(target_details.st_mode) or not os.access(target, os.X_OK):
        raise SafeError(stage=StageName.CONFIGURE, message="plugin Python executable is unsafe")
    return python, target


def _read_json(path: Path) -> Mapping[str, object] | None:
    try:
        details = path.lstat()
        if not stat.S_ISREG(details.st_mode) or details.st_uid != os.getuid():
            return None
        payload = json.loads(path.read_text())
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    raw_payload = cast(dict[object, object], payload)
    if not all(isinstance(key, str) for key in raw_payload):
        return None
    return cast(dict[str, object], payload)


def _write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
    parent = path.parent
    parent_details = parent.lstat()
    if stat.S_ISLNK(parent_details.st_mode) or not stat.S_ISDIR(parent_details.st_mode):
        raise SafeError(stage=StageName.CONFIGURE, message="runtime state directory is unsafe")
    if parent_details.st_uid != os.getuid():
        raise SafeError(
            stage=StageName.CONFIGURE,
            message="runtime state directory is not owned by the current user",
        )
    if path.exists() or path.is_symlink():
        target_details = path.lstat()
        if stat.S_ISLNK(target_details.st_mode) or not stat.S_ISREG(target_details.st_mode):
            raise SafeError(stage=StageName.CONFIGURE, message="runtime state file is unsafe")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


@contextmanager
def _provision_lock(runtime_root: Path) -> Generator[None, None, None]:
    lock_path = _runtime_directory(runtime_root) / "provision.lock"
    if lock_path.exists() or lock_path.is_symlink():
        details = lock_path.lstat()
        if stat.S_ISLNK(details.st_mode) or not stat.S_ISREG(details.st_mode):
            raise SafeError(stage=StageName.CONFIGURE, message="runtime provision lock is unsafe")
    with lock_path.open("a+") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _run_checked(
    runner: CommandRunner, argv: Sequence[str], env: Mapping[str, str] | None = None
) -> None:
    try:
        result = runner(argv, env=_sanitized_environment() if env is None else env, timeout_s=60.0)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as error:
        raise SafeError(
            stage=StageName.CONFIGURE, message=f"required command failed: {argv[0]}"
        ) from error
    if result.returncode != 0:
        raise SafeError(stage=StageName.CONFIGURE, message=f"required command failed: {argv[0]}")


def _venv_stamp_matches(venv_path: Path, lock_digest: str, system: SystemInfo) -> bool:
    _secure_venv_path(venv_path)
    python_values = _venv_python(venv_path)
    stamp = _read_json(venv_path / VENV_STAMP_FILENAME)
    if stamp is None or python_values is None:
        return False
    _, python_target = python_values
    return (
        stamp.get("schema") == STATE_SCHEMA_VERSION
        and stamp.get("runtime_version") == RUNTIME_VERSION
        and stamp.get("lock_digest") == lock_digest
        and stamp.get("python") == [system.python_major, system.python_minor]
        and stamp.get("python_target") == str(python_target)
    )


def _provision_venv(
    plugin_root: Path,
    venv_path: Path,
    lock_digest: str,
    system: SystemInfo,
    runner: CommandRunner,
) -> None:
    for command in (("uv", "--version"), ("ffmpeg", "-version"), ("ffprobe", "-version")):
        _run_checked(runner, command)
    environment = _sanitized_environment()
    environment["UV_PROJECT_ENVIRONMENT"] = str(venv_path)
    _run_checked(
        runner,
        (
            "uv",
            "sync",
            "--project",
            str(plugin_root),
            "--frozen",
            "--no-dev",
            "--all-extras",
            "--python",
            f"{system.python_major}.{system.python_minor}",
        ),
        environment,
    )
    _secure_venv_path(venv_path)
    python_values = _venv_python(venv_path)
    if python_values is None:
        raise SafeError(stage=StageName.CONFIGURE, message="plugin Python executable is missing")
    python, python_target = python_values
    validation_environment = dict(environment)
    validation_environment["PYTHONPATH"] = str(plugin_root / "scripts")
    _run_checked(
        runner, (str(python), "-P", "-c", "import audio_transcriber"), validation_environment
    )
    _write_json_atomic(
        venv_path / VENV_STAMP_FILENAME,
        {
            "schema": STATE_SCHEMA_VERSION,
            "runtime_version": RUNTIME_VERSION,
            "lock_digest": lock_digest,
            "python": [system.python_major, system.python_minor],
            "python_target": str(python_target),
        },
    )


def _cached_runtime(
    plugin_root: Path,
    runtime_root: Path,
    lock_digest: str,
    system: SystemInfo,
    recovery_attempt: bool,
) -> RuntimeHandle | None:
    base_fingerprint = _base_fingerprint(lock_digest, system)
    venv_path = plugin_root / VENV_DIRECTORY_NAME
    if not _venv_stamp_matches(venv_path, lock_digest, system):
        return None
    runtime_directory = _runtime_directory(runtime_root)
    index = _read_json(runtime_directory / "index.json")
    if index is None or index.get("schema") != STATE_SCHEMA_VERSION:
        return None
    if index.get("base_fingerprint") != base_fingerprint:
        return None
    try:
        backend = BackendFamily(_required_string(index, "backend"))
        compute_device = ComputeDevice(_required_string(index, "compute_device"))
        runtime_fingerprint = _required_string(index, "runtime_fingerprint")
    except ValueError:
        return None
    state_path = runtime_directory / runtime_fingerprint / "state.json"
    state = _read_json(state_path)
    if state is None or state.get("schema") != STATE_SCHEMA_VERSION:
        return None
    if (
        state.get("base_fingerprint") != base_fingerprint
        or state.get("runtime_fingerprint") != runtime_fingerprint
    ):
        return None
    if state.get("python") != str(venv_path / "bin" / "python"):
        return None
    return RuntimeHandle(
        runtime_fingerprint=runtime_fingerprint,
        base_fingerprint=base_fingerprint,
        python=venv_path / "bin" / "python",
        backend=backend,
        compute_device=compute_device,
        state_path=state_path,
        plugin_root=plugin_root,
        recovery_attempt=recovery_attempt,
    )


def _load_exclusions(runtime_root: Path, base_fingerprint: str) -> frozenset[RuntimeComponent]:
    payload = _read_json(_runtime_directory(runtime_root) / "unhealthy.json")
    if payload is None or payload.get("base_fingerprint") != base_fingerprint:
        return frozenset()
    components = payload.get("components")
    if not isinstance(components, list):
        return frozenset()
    try:
        values: list[RuntimeComponent] = []
        for component in cast(list[object], components):
            if not isinstance(component, str):
                return frozenset()
            values.append(RuntimeComponent(component))
        return frozenset(values)
    except ValueError:
        return frozenset()


def ensure_runtime(
    plugin_root: Path,
    reprobe: bool,
    runner: CommandRunner = _default_runner,
    *,
    system: SystemInfo | None = None,
    runtime_root: Path | None = None,
    input_path: Path | None = None,
) -> RuntimeHandle:
    """Return the one reusable plugin-owned environment and selected capability state."""
    root = plugin_root.resolve()
    active_system = _current_system() if system is None else system
    active_runtime_root = _runtime_root() if runtime_root is None else runtime_root
    if input_path is not None:
        validate_input_path(input_path)
        for command in (("uv", "--version"), ("ffmpeg", "-version"), ("ffprobe", "-version")):
            _run_checked(runner, command)
    _secure_private_directory(active_runtime_root)
    runtime_directory = _runtime_directory(active_runtime_root)
    _secure_venv_path(root / VENV_DIRECTORY_NAME)
    lock_digest = _lock_digest(root)
    recovery_attempt = os.environ.get(RUNTIME_RECOVERY_ATTEMPT_ENV) == "1"
    if not reprobe:
        cached = _cached_runtime(
            root, active_runtime_root, lock_digest, active_system, recovery_attempt
        )
        if cached is not None:
            return cached

    with _provision_lock(active_runtime_root):
        _secure_venv_path(root / VENV_DIRECTORY_NAME)
        if not _venv_stamp_matches(root / VENV_DIRECTORY_NAME, lock_digest, active_system):
            _provision_venv(root, root / VENV_DIRECTORY_NAME, lock_digest, active_system, runner)
        base_fingerprint = _base_fingerprint(lock_digest, active_system)
        unhealthy_path = runtime_directory / "unhealthy.json"
        if reprobe and unhealthy_path.exists():
            unhealthy_path.unlink()
        exclusions = _load_exclusions(active_runtime_root, base_fingerprint)
        report = probe_capabilities(runner, active_system, exclusions)
        runtime_fingerprint = _runtime_fingerprint(base_fingerprint, report)
        python = root / VENV_DIRECTORY_NAME / "bin" / "python"
        state_directory = _secure_child_directory(runtime_directory, runtime_fingerprint)
        state_path = state_directory / "state.json"
        _write_json_atomic(
            state_path,
            {
                "schema": STATE_SCHEMA_VERSION,
                "base_fingerprint": base_fingerprint,
                "runtime_fingerprint": runtime_fingerprint,
                "python": str(python),
                "capabilities": report.to_dict(),
            },
        )
        _write_json_atomic(
            runtime_directory / "index.json",
            {
                "schema": STATE_SCHEMA_VERSION,
                "base_fingerprint": base_fingerprint,
                "backend": report.selected_backend.value,
                "compute_device": report.compute_device.value,
                "runtime_fingerprint": runtime_fingerprint,
            },
        )
        return RuntimeHandle(
            runtime_fingerprint=runtime_fingerprint,
            base_fingerprint=base_fingerprint,
            python=python,
            backend=report.selected_backend,
            compute_device=report.compute_device,
            state_path=state_path,
            plugin_root=root,
            recovery_attempt=recovery_attempt,
        )


def mark_runtime_component_unhealthy(
    runtime: RuntimeHandle, component: RuntimeComponent, reason: str
) -> RecoveryTicket:
    """Persist one safe failed-component exclusion for bounded recovery."""
    if not reason:
        raise ValueError("reason must not be empty")
    root = _runtime_root()
    _secure_private_directory(root)
    runtime_directory = _runtime_directory(root)
    safe_reason = "runtime component marked unhealthy"
    with _provision_lock(root):
        existing = _load_exclusions(root, runtime.base_fingerprint)
        updated = sorted({*existing, component}, key=lambda item: item.value)
        _write_json_atomic(
            runtime_directory / "unhealthy.json",
            {
                "schema": STATE_SCHEMA_VERSION,
                "base_fingerprint": runtime.base_fingerprint,
                "components": [item.value for item in updated],
                "reason": safe_reason,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
        index = runtime_directory / "index.json"
        if index.exists():
            index.unlink()
    return RecoveryTicket(component=component, reason=safe_reason, recovery_attempt=True)


def reexec_after_component_failure(
    runtime: RuntimeHandle,
    component: RuntimeComponent,
    reason: str,
    argv: Sequence[str],
) -> NoReturn:
    """Retry startup once with the failed component excluded from capability selection."""
    if runtime.recovery_attempt:
        raise SafeError(
            stage=StageName.CONFIGURE,
            message="a runtime component already failed during recovery",
        )
    mark_runtime_component_unhealthy(runtime, component, reason)
    environment = _sanitized_environment()
    environment.pop(RUNTIME_BOOTSTRAPPED_ENV, None)
    environment[RUNTIME_RECOVERY_ATTEMPT_ENV] = "1"
    launcher = runtime.plugin_root / "scripts" / "transcribe_audio.py"
    os.execve(runtime.python, [str(runtime.python), str(launcher), *argv], environment)
    raise AssertionError("os.execve must not return")


def _same_executable(left: Path, right: Path) -> bool:
    try:
        return left.samefile(right)
    except OSError:
        return False


def launch(argv: Sequence[str]) -> NoReturn:
    """Provision if needed and re-exec the runtime interpreter exactly once."""
    reprobe = REPROBE_FLAG in argv
    forwarded = [argument for argument in argv if argument != REPROBE_FLAG]
    input_path = None
    if "--help" not in forwarded and "-h" not in forwarded:
        positional_arguments = [argument for argument in forwarded if not argument.startswith("-")]
        if positional_arguments:
            input_path = Path(positional_arguments[0])
    runtime = ensure_runtime(
        Path(__file__).resolve().parents[2],
        reprobe=reprobe,
        input_path=input_path,
    )
    current_executable = Path(sys.executable)
    if os.environ.get(RUNTIME_BOOTSTRAPPED_ENV) == runtime.runtime_fingerprint and _same_executable(
        current_executable, runtime.python
    ):
        from .cli import main

        raise SystemExit(main(forwarded))
    environment = _sanitized_environment()
    environment.pop(RUNTIME_BOOTSTRAPPED_ENV, None)
    environment[RUNTIME_BOOTSTRAPPED_ENV] = runtime.runtime_fingerprint
    environment["PYTHONPATH"] = str(runtime.plugin_root / "scripts")
    os.chdir(runtime.plugin_root)
    os.execve(
        runtime.python,
        [str(runtime.python), "-P", "-m", "audio_transcriber.cli", *forwarded],
        environment,
    )
    raise AssertionError("os.execve must not return")
