import json
import os
import stat
from typing import BinaryIO, cast
from pathlib import Path

import pytest

from audio_transcriber.config import ConfigOverrides, resolve_config
from audio_transcriber.models import Mode, StageName
from audio_transcriber.state import (
    PendingArtifact,
    RunStateStore,
    compute_input_identity,
    compute_run_fingerprint,
    verify_input_identity,
)


def _config(path: Path, **changes: object):
    values: dict[str, object] = {"input_path": path, "mode": Mode.LOCAL}
    values.update(changes)
    return resolve_config(ConfigOverrides(**values), path.parent)  # type: ignore[arg-type]


def _write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload)


def test_input_identity_canonicalizes_relative_and_symlink_spellings(tmp_path: Path) -> None:
    source = tmp_path / "recording.wav"
    source.write_bytes(b"audio" * 100)
    alias = tmp_path / "alias.wav"
    alias.symlink_to(source)

    direct = compute_input_identity(source)
    via_alias = compute_input_identity(alias)

    assert direct == via_alias
    assert direct.canonical_path == source.resolve()


def test_fingerprint_covers_transcription_and_render_inputs_but_not_control_flags(
    tmp_path: Path,
) -> None:
    source = tmp_path / "recording.wav"
    source.write_bytes(b"audio" * 100)
    identity = compute_input_identity(source)
    baseline = compute_run_fingerprint(identity, _config(source), "runtime-1")

    variants = (
        _config(source, mode=Mode.OPENAI),
        _config(source, local_model="other-model"),
        _config(source, language="ru"),
        _config(source, speakers=3),
        _config(source, diarization_revision="other-revision"),
        _config(source, max_chunk_duration_s=30),
        _config(source, overlap_s=1),
        _config(source, render_srt=True),
        _config(source, speaker_names="SPEAKER_00=Alice"),
    )

    assert all(
        compute_run_fingerprint(identity, variant, "runtime-1") != baseline for variant in variants
    )
    assert (
        compute_run_fingerprint(
            identity, _config(source, resume=False, overwrite=True), "runtime-1"
        )
        == baseline
    )
    assert compute_run_fingerprint(identity, _config(source), "runtime-2") != baseline


def test_input_identity_detects_file_changed_while_hashing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "recording.wav"
    source.write_bytes(b"a" * (6 * 1024 * 1024))
    original_open = Path.open

    def changing_open(self: Path, mode: str = "r", *args: object, **kwargs: object) -> BinaryIO:
        del args, kwargs
        handle = cast(BinaryIO, original_open(self, mode))
        if self == source:
            descriptor = os.open(source, os.O_WRONLY | os.O_TRUNC)
            try:
                os.write(descriptor, b"b" * (6 * 1024 * 1024))
            finally:
                os.close(descriptor)
        return handle

    monkeypatch.setattr(Path, "open", changing_open)

    with pytest.raises(ValueError, match="changed"):
        compute_input_identity(source)


def test_verify_input_identity_rejects_a_source_changed_after_run_selection(tmp_path: Path) -> None:
    source = tmp_path / "recording.wav"
    source.write_bytes(b"first")
    identity = compute_input_identity(source)
    source.write_bytes(b"second")

    with pytest.raises(ValueError, match="changed"):
        verify_input_identity(source, identity)


def test_commit_resume_invalidation_and_failure_evidence(tmp_path: Path) -> None:
    run_root = tmp_path / "runs" / "fingerprint"
    store = RunStateStore(run_root, "fingerprint")
    temp = run_root / "stages" / "01-inspect" / ".tmp-audio.json"
    _write(temp, '{"duration": 1}')

    with store.acquire():
        record = store.commit_stage(
            StageName.INSPECT,
            (
                PendingArtifact(
                    temp_path=temp,
                    final_relative_path=Path("stages/01-inspect/audio.json"),
                    validator=lambda path: json.loads(path.read_text()),
                ),
            ),
            {"backend": "local"},
        )
        assert record.stage is StageName.INSPECT
        resumed = store.get_valid_stage(
            StageName.INSPECT,
            lambda stage: json.loads((run_root / stage.artifacts[0]).read_text()),
        )
        assert resumed == {"duration": 1}
        failure_path = store.record_failure(StageName.ASR, {"code": "quality"})
        assert failure_path.parent.name == "failures"
        assert store.get_valid_stage(StageName.ASR, lambda _: None) is None
        store.invalidate_stage_and_descendants(StageName.INSPECT)

    assert not (run_root / "stages" / "01-inspect" / "audio.json").exists()
    assert store.get_valid_stage(StageName.INSPECT, lambda _: None) is None


def test_resume_rejects_invalid_manifest_and_digest_mismatch(tmp_path: Path) -> None:
    run_root = tmp_path / "runs" / "fingerprint"
    store = RunStateStore(run_root, "fingerprint")
    temp = run_root / "stages" / "01-inspect" / ".tmp-audio.json"
    _write(temp, "ok")

    with store.acquire():
        store.commit_stage(
            StageName.INSPECT,
            (
                PendingArtifact(
                    temp_path=temp,
                    final_relative_path=Path("stages/01-inspect/audio.txt"),
                    validator=lambda _: None,
                ),
            ),
            {},
        )

    final = run_root / "stages" / "01-inspect" / "audio.txt"
    final.write_text("tampered")
    assert store.get_valid_stage(StageName.INSPECT, lambda _: None) is None
    (run_root / "manifest.json").write_text("{")
    assert store.get_valid_stage(StageName.INSPECT, lambda _: None) is None


def test_run_state_directory_and_artifacts_are_private(tmp_path: Path) -> None:
    run_root = tmp_path / "runs" / "fingerprint"
    store = RunStateStore(run_root, "fingerprint")
    temp = run_root / "stages" / "01-inspect" / ".tmp-output"
    _write(temp, "ok")

    with store.acquire():
        store.commit_stage(
            StageName.INSPECT,
            (
                PendingArtifact(
                    temp_path=temp,
                    final_relative_path=Path("stages/01-inspect/output.txt"),
                    validator=lambda _: None,
                ),
            ),
            {},
        )

    assert stat.S_IMODE(os.stat(run_root).st_mode) == 0o700
    assert stat.S_IMODE(os.stat(run_root / "run.lock").st_mode) == 0o600
    assert stat.S_IMODE(os.stat(run_root / "manifest.json").st_mode) == 0o600


def test_run_state_rejects_symlinked_root(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    run_root = tmp_path / "runs" / "fingerprint"
    run_root.parent.mkdir()
    run_root.symlink_to(target, target_is_directory=True)

    with pytest.raises(ValueError, match="symlink"):
        RunStateStore(run_root, "fingerprint")
