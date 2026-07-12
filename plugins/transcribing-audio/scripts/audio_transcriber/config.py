"""Secret-safe configuration resolution for the transcription runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from dotenv import dotenv_values

from .constants import (
    DEFAULT_DIARIZATION_MODEL,
    DEFAULT_DIARIZATION_REVISION,
    DEFAULT_LOCAL_MODEL,
    DEFAULT_MAX_CHUNK_DURATION_S,
    DEFAULT_OPENAI_MODEL,
    DEFAULT_OVERLAP_S,
)
from .models import Mode, SpeakerCount


def _validate_path(path: Path, field: str) -> Path:
    if any(character in str(path) for character in ("\n", "\r", "\t", "\x00")):
        raise ValueError(f"{field} must not contain control characters")
    return path


def _optional_string(value: str | None, field: str, default: str) -> str:
    selected = default if value is None else value
    if not selected:
        raise ValueError(f"{field} must be a non-empty string")
    return selected


def _optional_bool(value: bool | None, default: bool, field: str) -> bool:
    selected = default if value is None else value
    del field
    return selected


def _optional_positive_float(value: float | None, default: float, field: str) -> float:
    selected = default if value is None else value
    if selected <= 0:
        raise ValueError(f"{field} must be a positive number")
    return float(selected)


def _parse_speaker_names(value: str | None) -> tuple[tuple[str, str], ...]:
    if value is None:
        return ()
    if not value:
        raise ValueError("speaker_names must use SPEAKER_00=Alice format")
    result: list[tuple[str, str]] = []
    labels: set[str] = set()
    names: set[str] = set()
    for raw_pair in value.split(","):
        label, separator, name = raw_pair.partition("=")
        label = label.strip()
        name = name.strip()
        if separator != "=" or not label or not name:
            raise ValueError("speaker_names must use SPEAKER_00=Alice format")
        if label in labels:
            raise ValueError("speaker_names cannot repeat a raw speaker label")
        if name in names:
            raise ValueError("speaker_names cannot repeat a display name")
        labels.add(label)
        names.add(name)
        result.append((label, name))
    return tuple(result)


@dataclass(frozen=True, slots=True)
class ConfigOverrides:
    input_path: Path
    mode: Mode | None = None
    env_file: Path | None = None
    output_dir: Path | None = None
    local_model: str | None = None
    openai_model: str | None = None
    diarization_model: str | None = None
    diarization_revision: str | None = None
    language: str | None = None
    speakers: int | None = None
    min_speakers: int | None = None
    max_speakers: int | None = None
    speaker_names: str | None = None
    max_chunk_duration_s: float | None = None
    overlap_s: float | None = None
    resume: bool | None = None
    overwrite: bool | None = None
    render_srt: bool | None = None
    render_vtt: bool | None = None


@dataclass(frozen=True, slots=True)
class Credentials:
    _openai_api_key: str | None = field(repr=False)
    _hf_token: str | None = field(repr=False)

    @property
    def openai_api_key(self) -> str | None:
        return self._openai_api_key

    @property
    def hf_token(self) -> str | None:
        return self._hf_token


@dataclass(frozen=True, slots=True)
class ResolvedConfig:
    input_path: Path
    output_dir: Path
    mode: Mode
    language: str | None
    local_model: str
    openai_model: str
    diarization_model: str
    diarization_revision: str
    speaker_count: SpeakerCount
    speaker_names: tuple[tuple[str, str], ...]
    max_chunk_duration_s: float
    overlap_s: float
    resume: bool
    overwrite: bool
    render_srt: bool
    render_vtt: bool
    credentials: Credentials = field(repr=False)

    def to_dict(self) -> dict[str, object]:
        return {
            "input_path": str(self.input_path),
            "output_dir": str(self.output_dir),
            "mode": self.mode.value,
            "language": self.language,
            "local_model": self.local_model,
            "openai_model": self.openai_model,
            "diarization_model": self.diarization_model,
            "diarization_revision": self.diarization_revision,
            "speaker_count": self.speaker_count.to_dict(),
            "speaker_names": [list(item) for item in self.speaker_names],
            "max_chunk_duration_s": self.max_chunk_duration_s,
            "overlap_s": self.overlap_s,
            "resume": self.resume,
            "overwrite": self.overwrite,
            "render_srt": self.render_srt,
            "render_vtt": self.render_vtt,
        }


def select_env_file(explicit: Path | None, repository_root: Path) -> Path | None:
    """Select one dotenv source without merging it with process environment."""
    _validate_path(repository_root, "repository_root")
    if explicit is not None:
        _validate_path(explicit, "env_file")
        if not explicit.is_file():
            raise ValueError(f"explicit env file does not exist: {explicit}")
        return explicit
    for name in (".env", ".env.prod"):
        candidate = repository_root / name
        if candidate.is_file():
            return candidate
    return None


def _credentials(env_file: Path | None) -> Credentials:
    values = dotenv_values(env_file, interpolate=False) if env_file is not None else {}

    def selected(name: str) -> str | None:
        value = values.get(name)
        return value if isinstance(value, str) and value else None

    return Credentials(_openai_api_key=selected("OPENAI_API_KEY"), _hf_token=selected("HF_TOKEN"))


def resolve_config(overrides: ConfigOverrides, repository_root: Path) -> ResolvedConfig:
    """Apply safe defaults, selected dotenv credentials, then CLI overrides."""
    input_path = _validate_path(overrides.input_path, "input_path")
    output_dir = _validate_path(
        overrides.output_dir if overrides.output_dir is not None else input_path.parent,
        "output_dir",
    )
    mode = Mode.LOCAL if overrides.mode is None else overrides.mode
    language = overrides.language
    if language is not None and not language:
        raise ValueError("language must be a non-empty string when provided")
    max_chunk_duration_s = _optional_positive_float(
        overrides.max_chunk_duration_s,
        DEFAULT_MAX_CHUNK_DURATION_S,
        "max_chunk_duration_s",
    )
    overlap_s = _optional_positive_float(overrides.overlap_s, DEFAULT_OVERLAP_S, "overlap_s")
    if overlap_s >= max_chunk_duration_s:
        raise ValueError("overlap_s must be smaller than max_chunk_duration_s")
    return ResolvedConfig(
        input_path=input_path,
        output_dir=output_dir,
        mode=mode,
        language=language,
        local_model=_optional_string(overrides.local_model, "local_model", DEFAULT_LOCAL_MODEL),
        openai_model=_optional_string(overrides.openai_model, "openai_model", DEFAULT_OPENAI_MODEL),
        diarization_model=_optional_string(
            overrides.diarization_model,
            "diarization_model",
            DEFAULT_DIARIZATION_MODEL,
        ),
        diarization_revision=_optional_string(
            overrides.diarization_revision,
            "diarization_revision",
            DEFAULT_DIARIZATION_REVISION,
        ),
        speaker_count=SpeakerCount(
            exact=overrides.speakers,
            minimum=overrides.min_speakers,
            maximum=overrides.max_speakers,
        ),
        speaker_names=_parse_speaker_names(overrides.speaker_names),
        max_chunk_duration_s=max_chunk_duration_s,
        overlap_s=overlap_s,
        resume=_optional_bool(overrides.resume, True, "resume"),
        overwrite=_optional_bool(overrides.overwrite, False, "overwrite"),
        render_srt=_optional_bool(overrides.render_srt, False, "render_srt"),
        render_vtt=_optional_bool(overrides.render_vtt, False, "render_vtt"),
        credentials=_credentials(select_env_file(overrides.env_file, repository_root)),
    )
