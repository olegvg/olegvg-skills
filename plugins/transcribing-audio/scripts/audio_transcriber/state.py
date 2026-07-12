"""Private, atomic, resumable state for a single transcription run."""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import stat
import tempfile
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeAlias, TypeVar, cast
from uuid import uuid4

from .config import ResolvedConfig
from .constants import STATE_SCHEMA_VERSION
from .models import InputIdentity, StageName

JsonValue: TypeAlias = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
FileValidator: TypeAlias = Callable[[Path], None]
T = TypeVar("T")
StageValidator: TypeAlias = Callable[["StageRecord"], T]

_SAMPLE_BLOCK_BYTES = 1024 * 1024
_FULL_SAMPLE_LIMIT_BYTES = 5 * 1024 * 1024
_MANIFEST_SCHEMA_VERSION = STATE_SCHEMA_VERSION
_STAGE_ORDER = tuple(StageName)
_SECRET_MARKERS = ("openai_api_key", "hf_token", "authorization", "bearer ")


def _canonical_json(payload: JsonValue) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_json(value: object) -> JsonValue:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("state JSON must not contain non-finite numbers")
        return value
    if isinstance(value, list):
        return [_validate_json(item) for item in cast(list[object], value)]
    if isinstance(value, dict):
        raw_value = cast(dict[object, object], value)
        result: dict[str, JsonValue] = {}
        for key, item in raw_value.items():
            if not isinstance(key, str):
                raise ValueError("state JSON object keys must be strings")
            _validate_safe_text(key)
            result[key] = _validate_json(item)
        return result
    raise ValueError("state JSON value is unsupported")


def _validate_safe_text(value: str) -> None:
    lower = value.lower()
    if any(marker in lower for marker in _SECRET_MARKERS):
        raise ValueError("state provenance must not contain credentials")
    if Path(value).is_absolute():
        raise ValueError("state provenance must not contain absolute paths")


def _safe_provenance(provenance: Mapping[str, JsonValue]) -> dict[str, JsonValue]:
    result = _validate_json(dict(provenance))
    if not isinstance(result, dict):  # pragma: no cover - fixed by dict() above
        raise AssertionError("provenance must be an object")

    def check(value: JsonValue) -> None:
        if isinstance(value, str):
            _validate_safe_text(value)
        elif isinstance(value, list):
            for item in value:
                check(item)
        elif isinstance(value, dict):
            for item in value.values():
                check(item)

    check(result)
    return result


def _regular_stat(path: Path) -> os.stat_result:
    try:
        path_stat = path.stat()
    except OSError as exc:
        raise ValueError("input audio cannot be inspected") from exc
    if not stat.S_ISREG(path_stat.st_mode):
        raise ValueError("input audio must be a regular file")
    return path_stat


def compute_input_identity(path: Path) -> InputIdentity:
    """Fingerprint content sampling while rejecting a source modified during hashing."""
    try:
        canonical_path = path.resolve(strict=True)
    except OSError as exc:
        raise ValueError("input audio does not exist") from exc
    initial = _regular_stat(canonical_path)
    digest = hashlib.sha256()
    digest.update(b"transcribing-audio-input-sample-v1\0")
    sample_offsets: tuple[int, ...]
    if initial.st_size < _FULL_SAMPLE_LIMIT_BYTES:
        sample_offsets = (0,)
    else:
        maximum_offset = max(initial.st_size - _SAMPLE_BLOCK_BYTES, 0)
        sample_offsets = tuple(
            min(maximum_offset, int(initial.st_size * fraction))
            for fraction in (0.0, 0.25, 0.50, 0.75, 1.0)
        )
    try:
        with canonical_path.open("rb") as handle:
            for offset in sample_offsets:
                handle.seek(offset)
                length = (
                    initial.st_size
                    if initial.st_size < _FULL_SAMPLE_LIMIT_BYTES
                    else _SAMPLE_BLOCK_BYTES
                )
                block = handle.read(length)
                digest.update(offset.to_bytes(8, "big"))
                digest.update(len(block).to_bytes(8, "big"))
                digest.update(block)
    except OSError as exc:
        raise ValueError("input audio cannot be read") from exc
    final = _regular_stat(canonical_path)
    if (
        initial.st_dev != final.st_dev
        or initial.st_ino != final.st_ino
        or initial.st_size != final.st_size
        or initial.st_mtime_ns != final.st_mtime_ns
    ):
        raise ValueError("input audio changed while it was being identified")
    return InputIdentity(
        canonical_path=canonical_path,
        size_bytes=initial.st_size,
        mtime_ns=initial.st_mtime_ns,
        sample_digest=digest.hexdigest(),
    )


def verify_input_identity(path: Path, expected: InputIdentity) -> InputIdentity:
    """Reject a source that changed after its run directory was selected."""
    actual = compute_input_identity(path)
    if actual != expected:
        raise ValueError("input audio changed after run state creation")
    return actual


def _fingerprint_config(config: ResolvedConfig) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {
        "mode": config.mode.value,
        "language": config.language,
        "local_model": config.local_model,
        "openai_model": config.openai_model,
        "diarization_model": config.diarization_model,
        "diarization_revision": config.diarization_revision,
        "speaker_count": _validate_json(config.speaker_count.to_dict()),
        "speaker_names": [list(item) for item in config.speaker_names],
        "max_chunk_duration_s": config.max_chunk_duration_s,
        "overlap_s": config.overlap_s,
        "render_srt": config.render_srt,
        "render_vtt": config.render_vtt,
    }
    return result


def compute_run_fingerprint(
    identity: InputIdentity, config: ResolvedConfig, runtime_fingerprint: str
) -> str:
    """Hash only data that changes reusable ASR, diarization, or rendering artifacts."""
    if not runtime_fingerprint:
        raise ValueError("runtime fingerprint must be non-empty")
    return hashlib.sha256(
        _canonical_json(
            cast(
                JsonValue,
                {
                    "input": _validate_json(identity.to_dict()),
                    "config": _fingerprint_config(config),
                    "runtime_fingerprint": runtime_fingerprint,
                },
            )
        )
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class PendingArtifact:
    temp_path: Path
    final_relative_path: Path
    validator: FileValidator


@dataclass(frozen=True, slots=True)
class StageRecord:
    schema_version: int
    stage: StageName
    run_fingerprint: str
    artifacts: tuple[Path, ...]
    artifact_sha256: Mapping[str, str]
    provenance: Mapping[str, JsonValue]
    completed_at: str

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "schema_version": self.schema_version,
            "stage": self.stage.value,
            "run_fingerprint": self.run_fingerprint,
            "artifacts": [str(path) for path in self.artifacts],
            "artifact_sha256": dict(self.artifact_sha256),
            "provenance": _safe_provenance(self.provenance),
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> StageRecord:
        expected = {
            "schema_version",
            "stage",
            "run_fingerprint",
            "artifacts",
            "artifact_sha256",
            "provenance",
            "completed_at",
        }
        if set(payload) != expected:
            raise ValueError("stage record schema is invalid")
        schema_version = payload["schema_version"]
        stage_value = payload["stage"]
        run_fingerprint = payload["run_fingerprint"]
        artifacts_value = payload["artifacts"]
        hashes_value = payload["artifact_sha256"]
        provenance_value = payload["provenance"]
        completed_at = payload["completed_at"]
        if (
            isinstance(schema_version, bool)
            or not isinstance(schema_version, int)
            or not isinstance(stage_value, str)
            or not isinstance(run_fingerprint, str)
            or not isinstance(artifacts_value, list)
            or not isinstance(hashes_value, dict)
            or not isinstance(provenance_value, dict)
            or not isinstance(completed_at, str)
        ):
            raise ValueError("stage record values are invalid")
        artifacts_values = cast(list[object], artifacts_value)
        artifacts = tuple(Path(item) for item in artifacts_values if isinstance(item, str))
        if len(artifacts) != len(artifacts_values) or not artifacts:
            raise ValueError("stage record artifacts are invalid")
        raw_hashes = cast(dict[object, object], hashes_value)
        hashes: dict[str, str] = {}
        for key, value in raw_hashes.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError("stage record digests are invalid")
            hashes[key] = value
        raw_provenance = cast(dict[object, object], provenance_value)
        if not all(isinstance(key, str) for key in raw_provenance):
            raise ValueError("stage record provenance is invalid")
        provenance = _safe_provenance(
            {cast(str, key): _validate_json(value) for key, value in raw_provenance.items()}
        )
        try:
            stage = StageName(stage_value)
        except ValueError as exc:
            raise ValueError("stage record stage is invalid") from exc
        return cls(
            schema_version=schema_version,
            stage=stage,
            run_fingerprint=run_fingerprint,
            artifacts=artifacts,
            artifact_sha256=hashes,
            provenance=provenance,
            completed_at=completed_at,
        )


def _relative_path(path: Path) -> Path:
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("state artifacts must use safe relative paths")
    return path


class RunStateStore:
    """Owns one private run root and publishes validated stages transactionally."""

    def __init__(self, run_root: Path, run_fingerprint: str) -> None:
        if not run_fingerprint:
            raise ValueError("run fingerprint must be non-empty")
        self._run_root = run_root
        self._run_fingerprint = run_fingerprint
        self._ensure_private_layout()

    @property
    def run_root(self) -> Path:
        return self._run_root

    def _ensure_private_layout(self) -> None:
        if self._run_root.is_symlink():
            raise ValueError("run state root must not be a symlink")
        self._run_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        for directory in (self._run_root, self._run_root / "stages", self._run_root / "failures"):
            directory.mkdir(mode=0o700, exist_ok=True)
            if directory.is_symlink() or not directory.is_dir():
                raise ValueError("run state directory is unsafe")
            if directory.stat().st_uid != os.getuid():
                raise ValueError("run state directory is not owned by the current user")
            os.chmod(directory, 0o700)

    def _path_from_relative(self, relative_path: Path) -> Path:
        relative = _relative_path(relative_path)
        destination = self._run_root / relative
        try:
            destination.relative_to(self._run_root)
        except ValueError as exc:  # pragma: no cover - Path joining normally prevents this
            raise ValueError("state artifact escapes the run root") from exc
        return destination

    @contextmanager
    def acquire(self) -> Generator[None, None, None]:
        """Serialize mutation of this fingerprint's state without locking other runs."""
        self._ensure_private_layout()
        lock_path = self._run_root / "run.lock"
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            os.chmod(lock_path, 0o600)
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _read_manifest(self) -> dict[str, object] | None:
        path = self._run_root / "manifest.json"
        if not path.exists():
            return {
                "schema_version": _MANIFEST_SCHEMA_VERSION,
                "run_fingerprint": self._run_fingerprint,
                "stages": {},
            }
        if path.is_symlink() or not path.is_file():
            return None
        try:
            value = cast(object, json.loads(path.read_text("utf-8")))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(value, dict):
            return None
        manifest = cast(dict[str, object], value)
        if set(manifest) != {"schema_version", "run_fingerprint", "stages"}:
            return None
        if (
            manifest.get("schema_version") != _MANIFEST_SCHEMA_VERSION
            or manifest.get("run_fingerprint") != self._run_fingerprint
            or not isinstance(manifest.get("stages"), dict)
        ):
            return None
        return manifest

    @staticmethod
    def _manifest_stages(manifest: Mapping[str, object]) -> dict[str, object]:
        raw_stages = manifest.get("stages")
        if not isinstance(raw_stages, dict):
            raise ValueError("run manifest stages are invalid")
        raw_mapping = cast(dict[object, object], raw_stages)
        if not all(isinstance(key, str) for key in raw_mapping):
            raise ValueError("run manifest stage keys are invalid")
        return {cast(str, key): value for key, value in raw_mapping.items()}

    def _write_manifest(self, manifest: Mapping[str, object]) -> None:
        payload = _canonical_json(_validate_json(dict(manifest)))
        descriptor, temp_name = tempfile.mkstemp(
            prefix=".tmp-manifest-", dir=self._run_root, text=False
        )
        temp_path = Path(temp_name)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self._run_root / "manifest.json")
            self._fsync_directory(self._run_root)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def get_valid_stage(self, stage: StageName, validator: StageValidator[T]) -> T | None:
        manifest = self._read_manifest()
        if manifest is None:
            return None
        try:
            stages = self._manifest_stages(manifest)
        except ValueError:
            return None
        value = stages.get(stage.value)
        if not isinstance(value, dict):
            return None
        try:
            record_value = cast(dict[str, object], value)
            record = StageRecord.from_dict(record_value)
            if (
                record.schema_version != _MANIFEST_SCHEMA_VERSION
                or record.run_fingerprint != self._run_fingerprint
            ):
                return None
            for relative_path in record.artifacts:
                artifact = self._path_from_relative(relative_path)
                expected_digest = record.artifact_sha256.get(str(relative_path))
                if (
                    expected_digest is None
                    or artifact.is_symlink()
                    or not artifact.is_file()
                    or _sha256_path(artifact) != expected_digest
                ):
                    return None
            return validator(record)
        except (OSError, ValueError):
            return None

    def commit_stage(
        self,
        stage: StageName,
        pending: Sequence[PendingArtifact],
        provenance: Mapping[str, JsonValue],
    ) -> StageRecord:
        if not pending:
            raise ValueError("a completed stage requires at least one artifact")
        manifest = self._read_manifest()
        if manifest is None:
            raise ValueError("run manifest is invalid; refusing to overwrite it")
        safe_provenance = _safe_provenance(provenance)
        seen: set[Path] = set()
        destinations: list[tuple[PendingArtifact, Path]] = []
        for artifact in pending:
            destination = self._path_from_relative(artifact.final_relative_path)
            if destination in seen:
                raise ValueError("stage artifacts cannot share a destination")
            seen.add(destination)
            try:
                artifact.temp_path.relative_to(self._run_root)
            except ValueError as exc:
                raise ValueError("temporary artifact escapes the run root") from exc
            if artifact.temp_path.is_symlink() or not artifact.temp_path.is_file():
                raise ValueError("temporary artifact is unsafe")
            artifact.validator(artifact.temp_path)
            self._fsync_file(artifact.temp_path)
            destinations.append((artifact, destination))

        backups: list[tuple[Path, Path]] = []
        created: list[Path] = []
        try:
            for _, destination in destinations:
                destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                os.chmod(destination.parent, 0o700)
                if destination.exists():
                    if destination.is_symlink() or not destination.is_file():
                        raise ValueError("existing stage artifact is unsafe")
                    backup = destination.with_name(f".{destination.name}.backup-{uuid4().hex}")
                    os.replace(destination, backup)
                    backups.append((destination, backup))
                else:
                    created.append(destination)
            for artifact, destination in destinations:
                os.replace(artifact.temp_path, destination)
                os.chmod(destination, 0o600)
                self._fsync_file(destination)
                self._fsync_directory(destination.parent)

            artifact_paths = tuple(artifact.final_relative_path for artifact, _ in destinations)
            record = StageRecord(
                schema_version=_MANIFEST_SCHEMA_VERSION,
                stage=stage,
                run_fingerprint=self._run_fingerprint,
                artifacts=artifact_paths,
                artifact_sha256={
                    str(artifact.final_relative_path): _sha256_path(destination)
                    for artifact, destination in destinations
                },
                provenance=safe_provenance,
                completed_at=datetime.now(UTC).isoformat(),
            )
            updated_stages = self._manifest_stages(manifest)
            updated_stages[stage.value] = record.to_dict()
            self._write_manifest(
                {
                    "schema_version": _MANIFEST_SCHEMA_VERSION,
                    "run_fingerprint": self._run_fingerprint,
                    "stages": updated_stages,
                }
            )
        except BaseException:
            for destination in reversed(created):
                if destination.exists() and not destination.is_symlink():
                    destination.unlink()
            for destination, backup in reversed(backups):
                if backup.exists():
                    os.replace(backup, destination)
            raise
        else:
            for _, backup in backups:
                if backup.exists():
                    backup.unlink()
            return record

    @staticmethod
    def _fsync_file(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def record_failure(self, stage: StageName, report: Mapping[str, JsonValue]) -> Path:
        safe_report = _safe_provenance(report)
        target = self._run_root / "failures" / f"{stage.value}-{uuid4().hex}.json"
        descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(_canonical_json({"stage": stage.value, "report": safe_report}))
            handle.flush()
            os.fsync(handle.fileno())
        self._fsync_directory(target.parent)
        return target

    def invalidate_stage_and_descendants(self, stage: StageName) -> None:
        manifest = self._read_manifest()
        if manifest is None:
            return
        try:
            updated = self._manifest_stages(manifest)
        except ValueError:
            return
        first = _STAGE_ORDER.index(stage)
        invalidate = {item.value for item in _STAGE_ORDER[first:]}
        for name in invalidate:
            value = updated.pop(name, None)
            if not isinstance(value, dict):
                continue
            try:
                record = StageRecord.from_dict(cast(dict[str, object], value))
            except ValueError:
                continue
            for relative_path in record.artifacts:
                try:
                    path = self._path_from_relative(relative_path)
                except ValueError:
                    continue
                if path.exists() and path.is_file() and not path.is_symlink():
                    path.unlink()
        self._write_manifest(
            {
                "schema_version": _MANIFEST_SCHEMA_VERSION,
                "run_fingerprint": self._run_fingerprint,
                "stages": updated,
            }
        )
