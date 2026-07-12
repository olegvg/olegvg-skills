"""Resumable six-stage transcription orchestration and safe final publishing."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import stat
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol, cast
from uuid import uuid4

from .alignment import align_words, merge_turns, rename_speakers
from .asr import merge_chunk_results
from .audio import (
    AudioTools,
    inspect_audio,
    materialize_chunk,
    measure_mean_volume_dbfs,
    normalize_for_diarization,
    plan_chunks,
    require_audio_tools,
)
from .bootstrap import RuntimeHandle
from .config import ResolvedConfig
from .constants import RUNTIME_ROOT_NAME, RUNTIME_VERSION
from .diarization import validate_diarization
from .errors import SafeError
from .interfaces import ASRBackend, CommandRunner, DiarizationBackend
from .models import (
    ASRChunkResult,
    ASROptions,
    ASRProvenance,
    AlignedWord,
    AudioChunk,
    AudioMetadata,
    ChunkingProvenance,
    DiarizationProvenance,
    DiarizationTurn,
    Mode,
    OutputPaths,
    QualityReport,
    StageName,
    TranscriptDocument,
    TranscriptProvenance,
    TranscriptTurn,
    UploadConsent,
    Word,
)
from .quality import QualityPolicy, evaluate_asr, recover_failed_chunks
from .renderers import (
    build_transcript_document,
    default_output_paths,
    load_json,
    render_json,
    render_srt,
    render_txt,
    render_vtt,
)
from .state import (
    PendingArtifact,
    RunStateStore,
    StageRecord,
    compute_input_identity,
    compute_run_fingerprint,
)


class OutputPublisher(Protocol):
    def __call__(
        self,
        rendered: RenderArtifact,
        final: OutputPaths,
        *,
        overwrite: bool,
        run_store: RunStateStore,
    ) -> OutputPaths: ...


@dataclass(frozen=True, slots=True)
class InspectArtifact:
    metadata: AudioMetadata
    normalized_audio: Path
    chunks: tuple[AudioChunk, ...]


@dataclass(frozen=True, slots=True)
class AsrArtifact:
    results: tuple[ASRChunkResult, ...]


@dataclass(frozen=True, slots=True)
class QualityArtifact:
    words: tuple[Word, ...]
    report: QualityReport
    retried_chunk_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DiarizationArtifact:
    turns: tuple[DiarizationTurn, ...]


@dataclass(frozen=True, slots=True)
class AlignmentArtifact:
    words: tuple[AlignedWord, ...]
    turns: tuple[TranscriptTurn, ...]


@dataclass(frozen=True, slots=True)
class RenderArtifact:
    document: TranscriptDocument
    staged_paths: OutputPaths


AsrFactory = Callable[[ResolvedConfig, RuntimeHandle, UploadConsent | None], ASRBackend]
DiarizerFactory = Callable[[ResolvedConfig, RuntimeHandle, float], DiarizationBackend]
Which = Callable[[str], str | None]


@dataclass(frozen=True, slots=True)
class PipelineDependencies:
    command_runner: CommandRunner
    which: Which
    asr_factory: AsrFactory
    diarizer_factory: DiarizerFactory
    clock: Callable[[], datetime]
    publisher: OutputPublisher


class RuntimeRecoveryRequired(Exception):
    """Signals the CLI to re-exec once after a local runtime health failure."""

    def __init__(self, component: str, error: SafeError) -> None:
        super().__init__(error.message)
        self.component = component
        self.error = error


def _private_root() -> Path:
    return Path("/tmp") / f"{RUNTIME_ROOT_NAME}-{os.getuid()}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_object(path: Path) -> dict[str, object]:
    try:
        decoded = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("stage JSON artifact cannot be read") from exc
    if not isinstance(decoded, dict):
        raise ValueError("stage JSON artifact must be an object")
    raw = cast(dict[object, object], decoded)
    if not all(isinstance(key, str) for key in raw):
        raise ValueError("stage JSON artifact must be an object")
    return {cast(str, key): value for key, value in raw.items()}


def _mapping_value(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    raw = cast(dict[object, object], value)
    if not all(isinstance(key, str) for key in raw):
        raise ValueError(f"{field} must be an object")
    return {cast(str, key): item for key, item in raw.items()}


def _object_list(value: object, field: str) -> tuple[dict[str, object], ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    return tuple(_mapping_value(item, f"{field} item") for item in cast(list[object], value))


def _write_object(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def _validate_json_artifact(path: Path) -> None:
    _read_object(path)


def _validate_regular_artifact(path: Path) -> None:
    if path.is_symlink() or not path.is_file() or path.stat().st_size <= 0:
        raise ValueError("stage artifact is invalid")


def _validate_transcript_json_artifact(path: Path) -> None:
    load_json(path)


def _stage_path(run_root: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("stage artifact path is unsafe")
    path = run_root / relative
    try:
        path.relative_to(run_root)
    except ValueError as exc:  # pragma: no cover - defensive Path invariant
        raise ValueError("stage artifact path escapes the run") from exc
    return path


def _record_file(record: StageRecord, run_root: Path, name: str) -> Path:
    for relative in record.artifacts:
        if str(relative) == name:
            path = _stage_path(run_root, relative)
            if path.is_symlink() or not path.is_file():
                raise ValueError("stage artifact is unsafe")
            return path
    raise ValueError("stage record is missing a required artifact")


def _stage_artifacts(record: StageRecord, stage: StageName) -> None:
    if record.stage is not stage:
        raise ValueError("stage record has an unexpected stage")


def _relative_chunk(chunk: AudioChunk) -> dict[str, object]:
    payload = chunk.to_dict()
    payload["path"] = f"chunks/{chunk.window.id}.flac"
    return payload


def validate_inspect_stage(record: StageRecord, *, run_root: Path | None = None) -> InspectArtifact:
    """Validate the committed inspect artifacts, including private chunk invariants."""
    _stage_artifacts(record, StageName.INSPECT)
    root = Path.cwd() if run_root is None else run_root
    stage_dir = root / "stages" / "01-inspect"
    payload = _read_object(_record_file(record, root, "stages/01-inspect/chunks.json"))
    if set(payload) != {"metadata", "normalized_audio", "chunks"}:
        raise ValueError("inspect artifact schema is invalid")
    metadata_value = payload["metadata"]
    normalized_value = payload["normalized_audio"]
    chunks_value = payload["chunks"]
    if (
        not isinstance(metadata_value, dict)
        or not isinstance(normalized_value, str)
        or not isinstance(chunks_value, list)
    ):
        raise ValueError("inspect artifact values are invalid")
    metadata = AudioMetadata.from_dict(_mapping_value(cast(object, metadata_value), "metadata"))
    normalized_relative = Path(normalized_value)
    if normalized_relative.is_absolute() or ".." in normalized_relative.parts:
        raise ValueError("normalized audio path is unsafe")
    normalized = stage_dir / normalized_relative
    if normalized != _record_file(record, root, "stages/01-inspect/diarization.wav"):
        raise ValueError("normalized audio path is inconsistent")
    chunks: list[AudioChunk] = []
    for raw_chunk in _object_list(cast(object, chunks_value), "chunks"):
        chunk_payload = dict(raw_chunk)
        path_value = chunk_payload.get("path")
        if not isinstance(path_value, str):
            raise ValueError("chunk path is invalid")
        relative = Path(path_value)
        if relative.is_absolute() or ".." in relative.parts or relative.parts[:1] != ("chunks",):
            raise ValueError("chunk path is unsafe")
        chunk_path = stage_dir / relative
        if chunk_path.is_symlink() or not chunk_path.is_file():
            raise ValueError("chunk artifact is unsafe")
        if stat.S_IMODE(chunk_path.stat().st_mode) != 0o600:
            raise ValueError("chunk artifact is not private")
        chunk_payload["path"] = str(chunk_path)
        chunk = AudioChunk.from_dict(chunk_payload)
        if chunk.size_bytes != chunk_path.stat().st_size or chunk.sha256 != _sha256(chunk_path):
            raise ValueError("chunk artifact digest is invalid")
        chunks.append(chunk)
    if not chunks:
        raise ValueError("inspect artifact has no chunks")
    return InspectArtifact(metadata=metadata, normalized_audio=normalized, chunks=tuple(chunks))


def validate_asr_stage(record: StageRecord, *, run_root: Path | None = None) -> AsrArtifact:
    _stage_artifacts(record, StageName.ASR)
    root = Path.cwd() if run_root is None else run_root
    payload = _read_object(_record_file(record, root, "stages/02-asr/asr-raw.json"))
    results = payload.get("results")
    if set(payload) != {"results"} or not isinstance(results, list):
        raise ValueError("ASR artifact schema is invalid")
    return AsrArtifact(
        results=tuple(
            ASRChunkResult.from_dict(item)
            for item in _object_list(cast(object, results), "results")
        )
    )


def validate_quality_stage(record: StageRecord, *, run_root: Path | None = None) -> QualityArtifact:
    _stage_artifacts(record, StageName.QUALITY)
    root = Path.cwd() if run_root is None else run_root
    words_payload = _read_object(_record_file(record, root, "stages/03-quality/asr-validated.json"))
    report_payload = _read_object(
        _record_file(record, root, "stages/03-quality/quality-report.json")
    )
    words = words_payload.get("words")
    retried = words_payload.get("retried_chunk_ids")
    report = report_payload.get("report")
    if (
        set(words_payload) != {"words", "retried_chunk_ids"}
        or set(report_payload) != {"report"}
        or not isinstance(words, list)
        or not isinstance(retried, list)
        or not isinstance(report, dict)
        or not all(isinstance(value, str) for value in cast(list[object], retried))
    ):
        raise ValueError("quality artifact schema is invalid")
    return QualityArtifact(
        words=tuple(Word.from_dict(value) for value in _object_list(cast(object, words), "words")),
        report=QualityReport.from_dict(_mapping_value(cast(object, report), "report")),
        retried_chunk_ids=tuple(cast(str, value) for value in cast(list[object], retried)),
    )


def validate_diarization_stage(
    record: StageRecord, *, run_root: Path | None = None
) -> DiarizationArtifact:
    _stage_artifacts(record, StageName.DIARIZE)
    root = Path.cwd() if run_root is None else run_root
    payload = _read_object(_record_file(record, root, "stages/04-diarize/diarization.json"))
    turns = payload.get("turns")
    if set(payload) != {"turns"} or not isinstance(turns, list):
        raise ValueError("diarization artifact schema is invalid")
    return DiarizationArtifact(
        turns=tuple(
            DiarizationTurn.from_dict(value) for value in _object_list(cast(object, turns), "turns")
        )
    )


def validate_alignment_stage(
    record: StageRecord, *, run_root: Path | None = None
) -> AlignmentArtifact:
    _stage_artifacts(record, StageName.ALIGN)
    root = Path.cwd() if run_root is None else run_root
    payload = _read_object(_record_file(record, root, "stages/05-align/aligned.json"))
    words = payload.get("words")
    turns = payload.get("turns")
    if (
        set(payload) != {"words", "turns"}
        or not isinstance(words, list)
        or not isinstance(turns, list)
    ):
        raise ValueError("alignment artifact schema is invalid")
    return AlignmentArtifact(
        words=tuple(
            AlignedWord.from_dict(value) for value in _object_list(cast(object, words), "words")
        ),
        turns=tuple(
            TranscriptTurn.from_dict(value) for value in _object_list(cast(object, turns), "turns")
        ),
    )


def validate_render_stage(record: StageRecord, *, run_root: Path | None = None) -> RenderArtifact:
    _stage_artifacts(record, StageName.RENDER)
    root = Path.cwd() if run_root is None else run_root
    json_path = _record_file(record, root, "stages/06-render/transcript.json")
    txt_path = _record_file(record, root, "stages/06-render/transcript.txt")
    srt = root / "stages/06-render/transcript.srt"
    vtt = root / "stages/06-render/transcript.vtt"
    srt_path = (
        srt
        if any(path == Path("stages/06-render/transcript.srt") for path in record.artifacts)
        else None
    )
    vtt_path = (
        vtt
        if any(path == Path("stages/06-render/transcript.vtt") for path in record.artifacts)
        else None
    )
    for path in (txt_path, srt_path, vtt_path):
        if path is not None and (
            path.is_symlink() or not path.is_file() or not path.read_text().strip()
        ):
            raise ValueError("render artifact is invalid")
    return RenderArtifact(
        document=load_json(json_path),
        staged_paths=OutputPaths(json_path, txt_path, srt_path, vtt_path),
    )


def _secure_directory(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    details = path.lstat()
    if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode):
        raise ValueError("output directory is unsafe")
    if details.st_uid != os.getuid():
        raise ValueError("output directory is not owned by the current user")
    os.chmod(path, 0o700)


def _validate_output_directory(paths: OutputPaths) -> None:
    parents = {path.parent for path in _output_values(paths)}
    if len(parents) != 1:
        raise ValueError("all transcript outputs must use one output directory")
    directory = next(iter(parents))
    if directory.exists() or directory.is_symlink():
        details = directory.lstat()
        if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode):
            raise ValueError("output directory is unsafe")
        if details.st_uid != os.getuid():
            raise ValueError("output directory is not owned by the current user")
    else:
        directory.mkdir(mode=0o700, parents=True)
    if not os.access(directory, os.W_OK | os.X_OK):
        raise ValueError("output directory is not writable")


def _output_values(paths: OutputPaths) -> tuple[Path, ...]:
    return tuple(path for path in (paths.json, paths.txt, paths.srt, paths.vtt) if path is not None)


def _private_file(path: Path) -> None:
    _owned_regular_file(path)
    os.chmod(path, 0o600)


def _owned_regular_file(path: Path) -> None:
    details = path.lstat()
    if stat.S_ISLNK(details.st_mode) or not stat.S_ISREG(details.st_mode):
        raise ValueError("output artifact is unsafe")
    if details.st_uid != os.getuid():
        raise ValueError("output artifact is not owned by the current user")


def _journal_root(run_store: RunStateStore) -> Path:
    # Runs are always placed at <private-root>/runs/<fingerprint> by PipelineRunner.
    root = run_store.run_root.parent.parent
    _secure_directory(root)
    return root


def _target_digest(paths: OutputPaths) -> str:
    payload = "\x00".join(sorted(str(path.absolute()) for path in _output_values(paths)))
    return hashlib.sha256(payload.encode()).hexdigest()


def _write_journal(path: Path, payload: Mapping[str, object]) -> None:
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    _write_object(temporary, payload)
    os.replace(temporary, path)


@contextmanager
def _output_lock(private_root: Path, digest: str) -> Generator[None, None, None]:
    directory = private_root / "output-locks"
    _secure_directory(directory)
    path = directory / f"{digest}.lock"
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def _temporary_target(target: Path, fingerprint: str, label: str) -> Path:
    return target.with_name(f".{target.stem}.{fingerprint}.{label}.{uuid4().hex}.tmp")


def _backup_target(target: Path, fingerprint: str, label: str) -> Path:
    return target.with_name(f".{target.stem}.{fingerprint}.{label}.{uuid4().hex}.backup")


def _copy_private(source: Path, target: Path) -> str:
    descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        with source.open("rb") as input_stream, os.fdopen(descriptor, "wb") as output_stream:
            shutil.copyfileobj(input_stream, output_stream)
            output_stream.flush()
            os.fsync(output_stream.fileno())
    except BaseException:
        if target.exists() and not target.is_symlink():
            target.unlink()
        raise
    _private_file(target)
    return _sha256(target)


def _journal_path(private_root: Path, digest: str) -> Path:
    directory = private_root / "publishes"
    _secure_directory(directory)
    return directory / f"{digest}.json"


def _safe_existing_target(path: Path) -> bool:
    if not (path.exists() or path.is_symlink()):
        return False
    _owned_regular_file(path)
    return True


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _restore_entries(entries: Sequence[Mapping[str, object]]) -> None:
    for entry in reversed(entries):
        target = Path(cast(str, entry["target"]))
        temporary = Path(cast(str, entry["temporary"]))
        backup_value = entry.get("backup")
        backup = Path(backup_value) if isinstance(backup_value, str) else None
        had_predecessor = bool(entry.get("had_predecessor"))
        if backup is not None and backup.exists() and not backup.is_symlink():
            if target.exists() and not target.is_symlink():
                target.unlink()
            os.replace(backup, target)
        elif not had_predecessor and target.exists() and not target.is_symlink():
            target.unlink()
        if temporary.exists() and not temporary.is_symlink():
            temporary.unlink()


def _recover_journal(final: OutputPaths, path: Path) -> None:
    if not path.exists():
        return
    _private_file(path)
    payload = _read_object(path)
    if payload.get("complete") is True:
        path.unlink()
        return
    entries_payload = _object_list(payload.get("entries"), "publish journal entries")
    expected = {str(value.absolute()) for value in _output_values(final)}
    actual = {str(Path(cast(str, item.get("target", ""))).absolute()) for item in entries_payload}
    if expected != actual:
        raise ValueError("publish journal target set is invalid")
    _restore_entries(entries_payload)
    path.unlink()


def recover_incomplete_publish(final: OutputPaths, run_store: RunStateStore) -> None:
    """Roll back only a journaled incomplete publish for this exact target set."""
    _validate_output_directory(final)
    private_root = _journal_root(run_store)
    digest = _target_digest(final)
    with _output_lock(private_root, digest):
        path = _journal_path(private_root, digest)
        _recover_journal(final, path)


def publish_outputs(
    rendered: RenderArtifact,
    final: OutputPaths,
    *,
    overwrite: bool,
    run_store: RunStateStore,
) -> OutputPaths:
    """Copy an already-validated Stage 6 set with rollback and crash recovery."""
    source_paths = _output_values(rendered.staged_paths)
    target_paths = _output_values(final)
    if len(source_paths) != len(target_paths):
        raise ValueError("staged and final transcript sets do not match")
    _validate_output_directory(final)
    for source in source_paths:
        _private_file(source)
        if source.stat().st_size == 0:
            raise ValueError("staged transcript artifact is empty")
    private_root = _journal_root(run_store)
    digest = _target_digest(final)
    fingerprint = run_store.run_root.name
    with _output_lock(private_root, digest):
        journal = _journal_path(private_root, digest)
        if journal.exists():
            _private_file(journal)
            payload = _read_object(journal)
            if payload.get("complete") is not True:
                _recover_journal(final, journal)
        entries: list[dict[str, object]] = []
        try:
            for index, (source, target) in enumerate(zip(source_paths, target_paths, strict=True)):
                existed = _safe_existing_target(target)
                if existed and not overwrite:
                    raise FileExistsError(f"final transcript already exists: {target}")
                temporary = _temporary_target(target, fingerprint, str(index))
                backup = _backup_target(target, fingerprint, str(index)) if existed else None
                entries.append(
                    {
                        "source": str(source.absolute()),
                        "target": str(target.absolute()),
                        "temporary": str(temporary.absolute()),
                        "backup": str(backup.absolute()) if backup is not None else None,
                        "digest": _copy_private(source, temporary),
                        "had_predecessor": existed,
                    }
                )
            journal_payload: dict[str, object] = {"complete": False, "entries": entries}
            _write_journal(journal, journal_payload)
            for entry in entries:
                target = Path(cast(str, entry["target"]))
                backup_value = entry["backup"]
                if isinstance(backup_value, str):
                    os.replace(target, Path(backup_value))
            for entry in entries:
                target = Path(cast(str, entry["target"]))
                temporary = Path(cast(str, entry["temporary"]))
                os.replace(temporary, target)
                _private_file(target)
                if _sha256(target) != entry["digest"]:
                    raise ValueError("published transcript digest is invalid")
            _fsync_directory(target_paths[0].parent)
            journal_payload["complete"] = True
            _write_journal(journal, journal_payload)
        except BaseException:
            _restore_entries(entries)
            raise
        else:
            for entry in entries:
                backup_value = entry["backup"]
                if isinstance(backup_value, str):
                    backup = Path(backup_value)
                    if backup.exists() and not backup.is_symlink():
                        backup.unlink()
            journal.unlink()
    return final


def _outputs_match(staged: OutputPaths, final: OutputPaths) -> bool:
    staged_paths = _output_values(staged)
    final_paths = _output_values(final)
    if len(staged_paths) != len(final_paths):
        return False
    try:
        for source, target in zip(staged_paths, final_paths, strict=True):
            _private_file(source)
            _owned_regular_file(target)
            if _sha256(source) != _sha256(target):
                return False
    except (OSError, ValueError):
        return False
    return True


class PipelineRunner:
    """Executes only validated predecessor artifacts and commits each stage atomically."""

    def __init__(
        self,
        runtime: RuntimeHandle,
        dependencies: PipelineDependencies,
        *,
        consent: UploadConsent | None = None,
        state_root: Path | None = None,
    ) -> None:
        self._runtime = runtime
        self._dependencies = dependencies
        self._consent = consent
        self._state_root = _private_root() if state_root is None else state_root

    def _store(self, config: ResolvedConfig) -> tuple[RunStateStore, str]:
        identity = compute_input_identity(config.input_path)
        fingerprint = compute_run_fingerprint(identity, config, self._runtime.runtime_fingerprint)
        return RunStateStore(self._state_root / "runs" / fingerprint, fingerprint), fingerprint

    def _commit_json(
        self,
        store: RunStateStore,
        stage: StageName,
        final_relative: Path,
        payload: Mapping[str, object],
        *,
        additional: Sequence[PendingArtifact] = (),
    ) -> None:
        temporary = (
            store.run_root / final_relative.parent / f".{final_relative.name}.{uuid4().hex}.tmp"
        )
        _write_object(temporary, payload)
        pending = (
            PendingArtifact(temporary, final_relative, _validate_json_artifact),
            *additional,
        )
        store.commit_stage(stage, pending, {"committed_at": self._dependencies.clock().isoformat()})

    @staticmethod
    def _stage_directory(store: RunStateStore, number: str) -> Path:
        path = store.run_root / "stages" / number
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
        return path

    def _reuse_or_build(
        self,
        store: RunStateStore,
        stage: StageName,
        validator: Callable[[StageRecord], object],
        build: Callable[[], object],
        *,
        resume: bool,
    ) -> object:
        if resume:
            value = store.get_valid_stage(stage, validator)
            if value is not None:
                return value
        store.invalidate_stage_and_descendants(stage)
        return build()

    def _preflight(
        self, config: ResolvedConfig
    ) -> tuple[AudioTools, AudioMetadata, ASRBackend, DiarizationBackend]:
        if not config.credentials.hf_token:
            raise SafeError(StageName.CONFIGURE, "HF_TOKEN is required for local diarization")
        if config.mode is Mode.OPENAI and not config.credentials.openai_api_key:
            raise SafeError(StageName.CONFIGURE, "OpenAI API key is required for OpenAI ASR")
        try:
            _validate_output_directory(
                default_output_paths(
                    config.input_path,
                    config.output_dir,
                    srt=config.render_srt,
                    vtt=config.render_vtt,
                )
            )
            tools = require_audio_tools(self._dependencies.which)
        except ValueError as exc:
            raise SafeError(StageName.CONFIGURE, str(exc)) from exc
        metadata = inspect_audio(config.input_path, self._dependencies.command_runner, tools)
        asr = self._dependencies.asr_factory(config, self._runtime, self._consent)
        diarizer = self._dependencies.diarizer_factory(config, self._runtime, metadata.duration_s)
        try:
            diarizer.health_check()
            if config.mode is Mode.LOCAL:
                asr.health_check(config.local_model)
            else:
                asr.health_check(config.openai_model)
        except SafeError as exc:
            component = "diarization" if exc.stage is StageName.DIARIZE else "asr"
            raise RuntimeRecoveryRequired(component, exc) from exc
        return tools, metadata, asr, diarizer

    def run(self, config: ResolvedConfig) -> OutputPaths:
        store, fingerprint = self._store(config)
        with store.acquire():
            final = default_output_paths(
                config.input_path, config.output_dir, srt=config.render_srt, vtt=config.render_vtt
            )
            recover_incomplete_publish(final, store)
            tools, metadata, asr, diarizer = self._preflight(config)
            if not config.resume:
                store.invalidate_stage_and_descendants(StageName.INSPECT)

            def build_inspect() -> InspectArtifact:
                directory = self._stage_directory(store, "01-inspect")
                normalized = directory / f".diarization.{uuid4().hex}.wav"
                normalize_for_diarization(
                    config.input_path, normalized, self._dependencies.command_runner, tools
                )
                os.chmod(normalized, 0o600)
                chunks: list[AudioChunk] = []
                pending: list[PendingArtifact] = [
                    PendingArtifact(
                        normalized,
                        Path("stages/01-inspect/diarization.wav"),
                        _validate_regular_artifact,
                    )
                ]
                for window in plan_chunks(
                    metadata,
                    max_duration_s=config.max_chunk_duration_s,
                    overlap_s=config.overlap_s,
                ):
                    temporary = directory / "chunks" / f".{window.id}.{uuid4().hex}.flac"
                    temporary.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                    chunk = materialize_chunk(
                        normalized, window, temporary, self._dependencies.command_runner, tools
                    )
                    os.chmod(temporary, 0o600)
                    chunks.append(chunk)
                    pending.append(
                        PendingArtifact(
                            temporary,
                            Path(f"stages/01-inspect/chunks/{window.id}.flac"),
                            _validate_regular_artifact,
                        )
                    )
                chunks_payload = {
                    "metadata": metadata.to_dict(),
                    "normalized_audio": "diarization.wav",
                    "chunks": [_relative_chunk(chunk) for chunk in chunks],
                }
                temporary_json = directory / f".chunks.{uuid4().hex}.json"
                _write_object(temporary_json, chunks_payload)
                store.commit_stage(
                    StageName.INSPECT,
                    (
                        PendingArtifact(
                            temporary_json,
                            Path("stages/01-inspect/chunks.json"),
                            _validate_json_artifact,
                        ),
                        *pending,
                    ),
                    {"committed_at": self._dependencies.clock().isoformat()},
                )
                record = store.get_valid_stage(
                    StageName.INSPECT,
                    lambda item: validate_inspect_stage(item, run_root=store.run_root),
                )
                if record is None:  # pragma: no cover - commit contract
                    raise ValueError("inspect stage did not validate after commit")
                return record

            inspect = cast(
                InspectArtifact,
                self._reuse_or_build(
                    store,
                    StageName.INSPECT,
                    lambda item: validate_inspect_stage(item, run_root=store.run_root),
                    build_inspect,
                    resume=config.resume,
                ),
            )

            def build_asr() -> AsrArtifact:
                results = tuple(
                    asr.transcribe(
                        chunk,
                        ASROptions(
                            config.local_model
                            if config.mode is Mode.LOCAL
                            else config.openai_model,
                            config.language,
                            beam_size=5 if config.mode is Mode.LOCAL else None,
                        ),
                    )
                    for chunk in inspect.chunks
                )
                self._commit_json(
                    store,
                    StageName.ASR,
                    Path("stages/02-asr/asr-raw.json"),
                    {"results": [result.to_dict() for result in results]},
                )
                return AsrArtifact(results)

            asr_artifact = cast(
                AsrArtifact,
                self._reuse_or_build(
                    store,
                    StageName.ASR,
                    lambda item: validate_asr_stage(item, run_root=store.run_root),
                    build_asr,
                    resume=config.resume,
                ),
            )

            def build_quality() -> QualityArtifact:
                policy = QualityPolicy()
                report = evaluate_asr(
                    inspect.chunks,
                    asr_artifact.results,
                    source_duration_s=inspect.metadata.duration_s,
                    policy=policy,
                    mean_volume_dbfs=lambda chunk: measure_mean_volume_dbfs(
                        chunk, self._dependencies.command_runner, tools
                    ),
                )
                final_results = asr_artifact.results
                retried: tuple[str, ...] = ()
                if report.status == "failed":
                    directory = self._stage_directory(store, "03-quality")

                    def materialize(parent: AudioChunk, window: object) -> AudioChunk:
                        from .models import AudioWindow

                        if not isinstance(
                            window, AudioWindow
                        ):  # pragma: no cover - typed recovery contract
                            raise ValueError("recovery window is invalid")
                        target = directory / "retries" / f".{window.id}.{uuid4().hex}.flac"
                        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                        chunk = materialize_chunk(
                            inspect.normalized_audio,
                            window,
                            target,
                            self._dependencies.command_runner,
                            tools,
                        )
                        os.chmod(target, 0o600)
                        return chunk

                    def retry(chunk: AudioChunk, options: object) -> ASRChunkResult:
                        from .quality import RecoveryOptions

                        if not isinstance(
                            options, RecoveryOptions
                        ):  # pragma: no cover - typed recovery contract
                            raise ValueError("recovery options are invalid")
                        return asr.transcribe(
                            chunk,
                            ASROptions(
                                config.local_model
                                if config.mode is Mode.LOCAL
                                else config.openai_model,
                                options.language,
                                temperature=options.temperature,
                                beam_size=options.beam_size,
                            ),
                        )

                    recovery = recover_failed_chunks(
                        asr_artifact.results,
                        report,
                        retry,
                        policy,
                        planned_chunks=inspect.chunks,
                        source_duration_s=inspect.metadata.duration_s,
                        mean_volume_dbfs=lambda chunk: measure_mean_volume_dbfs(
                            chunk, self._dependencies.command_runner, tools
                        ),
                        materialize=materialize,
                        state_store=store,
                    )
                    replacements = {
                        result.chunk.window.id: result for result in recovery.replacement_results
                    }
                    final_results = tuple(
                        replacements.get(result.chunk.window.id, result)
                        for result in asr_artifact.results
                    )
                    report = recovery.final_report
                    retried = recovery.retried_ids
                    for file in (directory / "retries").glob("*.flac"):
                        if file.is_file() and not file.is_symlink():
                            file.unlink()
                words = merge_chunk_results(final_results)
                self._commit_json(
                    store,
                    StageName.QUALITY,
                    Path("stages/03-quality/asr-validated.json"),
                    {
                        "words": [word.to_dict() for word in words],
                        "retried_chunk_ids": list(retried),
                    },
                    additional=(
                        PendingArtifact(
                            self._json_temp(
                                store,
                                Path("stages/03-quality/quality-report.json"),
                                {"report": report.to_dict()},
                            ),
                            Path("stages/03-quality/quality-report.json"),
                            _validate_json_artifact,
                        ),
                    ),
                )
                return QualityArtifact(words, report, retried)

            quality = cast(
                QualityArtifact,
                self._reuse_or_build(
                    store,
                    StageName.QUALITY,
                    lambda item: validate_quality_stage(item, run_root=store.run_root),
                    build_quality,
                    resume=config.resume,
                ),
            )

            def build_diarization() -> DiarizationArtifact:
                turns = diarizer.diarize(inspect.normalized_audio, config.speaker_count)
                validate_diarization(
                    turns, duration_s=inspect.metadata.duration_s, speakers=config.speaker_count
                )
                self._commit_json(
                    store,
                    StageName.DIARIZE,
                    Path("stages/04-diarize/diarization.json"),
                    {"turns": [turn.to_dict() for turn in turns]},
                )
                return DiarizationArtifact(turns)

            diarization = cast(
                DiarizationArtifact,
                self._reuse_or_build(
                    store,
                    StageName.DIARIZE,
                    lambda item: validate_diarization_stage(item, run_root=store.run_root),
                    build_diarization,
                    resume=config.resume,
                ),
            )

            def build_alignment() -> AlignmentArtifact:
                words = rename_speakers(
                    align_words(quality.words, diarization.turns), dict(config.speaker_names)
                )
                turns = merge_turns(words)
                self._commit_json(
                    store,
                    StageName.ALIGN,
                    Path("stages/05-align/aligned.json"),
                    {
                        "words": [word.to_dict() for word in words],
                        "turns": [turn.to_dict() for turn in turns],
                    },
                )
                return AlignmentArtifact(words, turns)

            alignment = cast(
                AlignmentArtifact,
                self._reuse_or_build(
                    store,
                    StageName.ALIGN,
                    lambda item: validate_alignment_stage(item, run_root=store.run_root),
                    build_alignment,
                    resume=config.resume,
                ),
            )

            def build_render() -> RenderArtifact:
                backend = next(
                    (result.backend for result in asr_artifact.results), config.mode.value
                )
                model = config.local_model if config.mode is Mode.LOCAL else config.openai_model
                language = next(
                    (result.language for result in asr_artifact.results if result.language),
                    config.language,
                )
                document = build_transcript_document(
                    input_identity=compute_input_identity(config.input_path),
                    duration_s=inspect.metadata.duration_s,
                    language=language,
                    asr=ASRProvenance(
                        config.mode,
                        backend,
                        model,
                        ChunkingProvenance(config.max_chunk_duration_s, config.overlap_s),
                        language,
                    ),
                    diarization=DiarizationProvenance(
                        config.diarization_model,
                        config.diarization_revision,
                        self._runtime.compute_device,
                        config.speaker_count,
                    ),
                    provenance=TranscriptProvenance(
                        RUNTIME_VERSION,
                        fingerprint,
                        (
                            StageName.INSPECT,
                            StageName.ASR,
                            StageName.QUALITY,
                            StageName.DIARIZE,
                            StageName.ALIGN,
                            StageName.RENDER,
                        ),
                        quality.retried_chunk_ids,
                    ),
                    diarization_turns=diarization.turns,
                    turns=alignment.turns,
                    quality=quality.report,
                    speaker_names=dict(config.speaker_names),
                )
                directory = self._stage_directory(store, "06-render")
                temporary_json = directory / f".transcript.{uuid4().hex}.json"
                temporary_txt = directory / f".transcript.{uuid4().hex}.txt"
                render_json(document, temporary_json)
                render_txt(document, temporary_txt)
                pending: list[PendingArtifact] = [
                    PendingArtifact(
                        temporary_json,
                        Path("stages/06-render/transcript.json"),
                        _validate_transcript_json_artifact,
                    ),
                    PendingArtifact(
                        temporary_txt,
                        Path("stages/06-render/transcript.txt"),
                        _validate_regular_artifact,
                    ),
                ]
                if config.render_srt:
                    temporary_srt = directory / f".transcript.{uuid4().hex}.srt"
                    render_srt(document, temporary_srt)
                    pending.append(
                        PendingArtifact(
                            temporary_srt,
                            Path("stages/06-render/transcript.srt"),
                            _validate_regular_artifact,
                        )
                    )
                if config.render_vtt:
                    temporary_vtt = directory / f".transcript.{uuid4().hex}.vtt"
                    render_vtt(document, temporary_vtt)
                    pending.append(
                        PendingArtifact(
                            temporary_vtt,
                            Path("stages/06-render/transcript.vtt"),
                            _validate_regular_artifact,
                        )
                    )
                store.commit_stage(
                    StageName.RENDER,
                    pending,
                    {"committed_at": self._dependencies.clock().isoformat()},
                )
                valid = store.get_valid_stage(
                    StageName.RENDER,
                    lambda item: validate_render_stage(item, run_root=store.run_root),
                )
                if valid is None:  # pragma: no cover - commit contract
                    raise ValueError("render stage did not validate after commit")
                return valid

            rendered = cast(
                RenderArtifact,
                self._reuse_or_build(
                    store,
                    StageName.RENDER,
                    lambda item: validate_render_stage(item, run_root=store.run_root),
                    build_render,
                    resume=config.resume,
                ),
            )
            if _outputs_match(rendered.staged_paths, final):
                return final
            return self._dependencies.publisher(
                rendered, final, overwrite=config.overwrite, run_store=store
            )

    @staticmethod
    def _json_temp(store: RunStateStore, relative: Path, payload: Mapping[str, object]) -> Path:
        temporary = store.run_root / relative.parent / f".{relative.name}.{uuid4().hex}.tmp"
        _write_object(temporary, payload)
        return temporary
