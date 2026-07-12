"""Strict canonical transcript validation and derived human-readable renderers."""

from __future__ import annotations

import json
import math
import os
import re
import unicodedata
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

from .alignment import join_word_text
from .constants import OUTPUT_SCHEMA_VERSION
from .diarization import validate_diarization
from .models import (
    ASRProvenance,
    DiarizationProvenance,
    DiarizationTurn,
    InputIdentity,
    OutputPaths,
    QualityReport,
    TranscriptDocument,
    TranscriptProvenance,
    TranscriptSpeaker,
    TranscriptTurn,
)

_TIMESTAMP_TOLERANCE_S = 0.05
_TXT_LINE = re.compile(r"^\[\d{2,}:\d{2}:\d{2}–\d{2,}:\d{2}:\d{2}\] .+: .+$")
_SRT_TIMESTAMP = re.compile(r"^\d{2,}:\d{2}:\d{2},\d{3}$")
_VTT_TIMESTAMP = re.compile(r"^\d{2,}:\d{2}:\d{2}\.\d{3}$")


def _validate_display_name(name: object) -> str:
    if not isinstance(name, str) or not name.strip():
        raise ValueError("speaker display names must not be empty")
    if any(unicodedata.category(character).startswith("C") for character in name):
        raise ValueError("speaker display names must not contain control characters")
    return name


def _validate_document_speakers(document: TranscriptDocument) -> dict[str, str]:
    if not document.speakers:
        raise ValueError("transcript document must contain diarization speakers")
    raw_labels = [speaker.raw_label for speaker in document.speakers]
    display_names = [speaker.display_name for speaker in document.speakers]
    if raw_labels != sorted(raw_labels) or len(set(raw_labels)) != len(raw_labels):
        raise ValueError("transcript speaker labels must be sorted and unique")
    if len(set(display_names)) != len(display_names):
        raise ValueError("transcript speaker display names must be unique")
    for display_name in display_names:
        _validate_display_name(display_name)
    return dict(zip(raw_labels, display_names, strict=True))


def _validate_turns(document: TranscriptDocument, speakers: Mapping[str, str]) -> None:
    if not document.turns:
        raise ValueError("transcript document must contain at least one turn")
    previous_word_end: float | None = None
    previous_turn_start = -math.inf
    for turn in document.turns:
        if turn.start_s < 0 or turn.end_s > document.duration_s:
            raise ValueError("transcript turn is outside the input duration")
        if turn.start_s + _TIMESTAMP_TOLERANCE_S < previous_turn_start:
            raise ValueError("transcript turns are not chronological")
        previous_turn_start = turn.start_s
        if speakers.get(turn.raw_speaker) != turn.speaker:
            raise ValueError("transcript turn references an unknown or mismatched speaker")
        if not turn.text.strip():
            raise ValueError("transcript turn text must not be empty")
        if turn.text != join_word_text(turn.words):
            raise ValueError("transcript turn text does not match deterministic word joining")
        for aligned in turn.words:
            word = aligned.word
            if aligned.raw_speaker != turn.raw_speaker or aligned.speaker != turn.speaker:
                raise ValueError("transcript turn words must retain the turn speaker labels")
            if word.start_s < turn.start_s or word.end_s > turn.end_s:
                raise ValueError("transcript turn must bound every word timestamp")
            if (
                previous_word_end is not None
                and word.start_s < previous_word_end - _TIMESTAMP_TOLERANCE_S
            ):
                raise ValueError("transcript words are unsorted or overlap beyond tolerance")
            previous_word_end = word.end_s


def validate_transcript(document: TranscriptDocument) -> None:
    """Reject documents that cannot safely become published canonical output."""
    if document.schema_version != OUTPUT_SCHEMA_VERSION:
        raise ValueError("transcript schema version is unsupported")
    if not math.isfinite(document.duration_s) or document.duration_s < 0:
        raise ValueError("transcript duration must be finite and non-negative")
    if document.quality.status != "passed" or document.quality.unresolved_errors:
        raise ValueError("transcript quality must be passed without unresolved errors")
    speaker_by_raw = _validate_document_speakers(document)
    if document.diarization.speaker_count.exact is not None and len(speaker_by_raw) != (
        document.diarization.speaker_count.exact
    ):
        raise ValueError("transcript exact speaker count does not match diarization labels")
    _validate_turns(document, speaker_by_raw)


def build_transcript_document(
    *,
    input_identity: InputIdentity,
    duration_s: float,
    language: str | None,
    asr: ASRProvenance,
    diarization: DiarizationProvenance,
    provenance: TranscriptProvenance,
    diarization_turns: Sequence[DiarizationTurn],
    turns: Sequence[TranscriptTurn],
    quality: QualityReport,
    speaker_names: Mapping[str, str],
) -> TranscriptDocument:
    """Build one canonical document from already-validated stage artifacts."""
    validate_diarization(
        diarization_turns,
        duration_s=duration_s,
        speakers=diarization.speaker_count,
    )
    raw_labels = tuple(sorted({turn.raw_speaker for turn in diarization_turns}))
    unknown_names = set(speaker_names).difference(raw_labels)
    if unknown_names:
        raise ValueError("speaker name mapping contains an unknown raw label")
    turn_display_names: dict[str, set[str]] = {}
    for turn in turns:
        turn_display_names.setdefault(turn.raw_speaker, set()).add(turn.speaker)
    speakers: list[TranscriptSpeaker] = []
    mismatched_turn_labels: list[str] = []
    for raw_label in raw_labels:
        names = turn_display_names.get(raw_label, set())
        if len(names) > 1:
            raise ValueError("a raw speaker label has conflicting display names")
        display_name = speaker_names.get(raw_label, next(iter(names), raw_label))
        speakers.append(TranscriptSpeaker(raw_label, _validate_display_name(display_name)))
        if names and display_name not in names:
            mismatched_turn_labels.append(raw_label)
    if len({speaker.display_name for speaker in speakers}) != len(speakers):
        raise ValueError("speaker name mapping has duplicate display names")
    if mismatched_turn_labels:
        raise ValueError("turn speaker names must match the display-name mapping")
    document = TranscriptDocument(
        schema_version=OUTPUT_SCHEMA_VERSION,
        input_identity=input_identity,
        duration_s=duration_s,
        language=language,
        asr=asr,
        diarization=diarization,
        provenance=provenance,
        speakers=tuple(speakers),
        turns=tuple(turns),
        quality=quality,
    )
    validate_transcript(document)
    return document


def _require_output_filename(path: Path) -> None:
    if not path.name:
        raise ValueError("output path must include a filename")


def _write_private_text(path: Path, content: str) -> Path:
    _require_output_filename(path)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.fchmod(descriptor, 0o600)
    except Exception:
        os.close(descriptor)
        raise
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
        output.write(content)
    if path.stat().st_size == 0:
        raise ValueError("rendered transcript output must not be empty")
    return path


def render_json(document: TranscriptDocument, path: Path) -> Path:
    """Write canonical UTF-8 JSON, then parse and validate it before returning."""
    validate_transcript(document)
    serialized = json.dumps(document.to_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    _write_private_text(path, serialized)
    if load_json(path) != document:
        raise ValueError("canonical transcript JSON did not round-trip")
    return path


def load_json(path: Path) -> TranscriptDocument:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("canonical transcript JSON cannot be read") from exc
    if not isinstance(parsed, dict):
        raise ValueError("canonical transcript JSON must be an object")
    raw_payload = cast(dict[object, object], parsed)
    if not all(isinstance(key, str) for key in raw_payload):
        raise ValueError("canonical transcript JSON must be an object")
    document = TranscriptDocument.from_dict(cast(dict[str, object], raw_payload))
    validate_transcript(document)
    return document


def _whole_second_timestamp(seconds: float, *, ceiling: bool) -> str:
    value = math.ceil(seconds) if ceiling else math.floor(seconds)
    hours, remainder = divmod(value, 3600)
    minutes, seconds_part = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds_part:02d}"


def _millisecond_timestamp(seconds: float, *, separator: str) -> str:
    milliseconds = round(seconds * 1000)
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds_part, milliseconds_part = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds_part:02d}{separator}{milliseconds_part:03d}"


def _render_turn_line(turn: TranscriptTurn) -> str:
    return f"{turn.speaker}: {turn.text}"


def render_txt(document: TranscriptDocument, path: Path) -> Path:
    validate_transcript(document)
    lines = tuple(
        "["
        f"{_whole_second_timestamp(turn.start_s, ceiling=False)}–"
        f"{_whole_second_timestamp(turn.end_s, ceiling=True)}] "
        f"{_render_turn_line(turn)}"
        for turn in document.turns
    )
    if not all(_TXT_LINE.fullmatch(line) for line in lines):
        raise ValueError("TXT transcript format validation failed")
    return _write_private_text(path, "\n".join(lines) + "\n")


def render_srt(document: TranscriptDocument, path: Path) -> Path:
    validate_transcript(document)
    cues = tuple(
        "\n".join(
            (
                str(index),
                f"{_millisecond_timestamp(turn.start_s, separator=',')} --> "
                f"{_millisecond_timestamp(turn.end_s, separator=',')}",
                _render_turn_line(turn),
            )
        )
        for index, turn in enumerate(document.turns, start=1)
    )
    content = "\n\n".join(cues) + "\n"
    for cue in cues:
        _, timestamp, text = cue.split("\n")
        start, end = timestamp.split(" --> ")
        if not _SRT_TIMESTAMP.fullmatch(start) or not _SRT_TIMESTAMP.fullmatch(end) or not text:
            raise ValueError("SRT transcript format validation failed")
    return _write_private_text(path, content)


def render_vtt(document: TranscriptDocument, path: Path) -> Path:
    validate_transcript(document)
    cues = tuple(
        "\n".join(
            (
                f"{_millisecond_timestamp(turn.start_s, separator='.')} --> "
                f"{_millisecond_timestamp(turn.end_s, separator='.')}",
                _render_turn_line(turn),
            )
        )
        for turn in document.turns
    )
    content = "WEBVTT\n\n" + "\n\n".join(cues) + "\n"
    for cue in cues:
        timestamp, text = cue.split("\n")
        start, end = timestamp.split(" --> ")
        if not _VTT_TIMESTAMP.fullmatch(start) or not _VTT_TIMESTAMP.fullmatch(end) or not text:
            raise ValueError("VTT transcript format validation failed")
    return _write_private_text(path, content)


def default_output_paths(
    input_path: Path, output_dir: Path, *, srt: bool, vtt: bool
) -> OutputPaths:
    if not input_path.name or not input_path.stem:
        raise ValueError("input path must include a filename")
    stem = input_path.stem
    return OutputPaths(
        json=output_dir / f"{stem}.transcript.json",
        txt=output_dir / f"{stem}.transcript.txt",
        srt=output_dir / f"{stem}.transcript.srt" if srt else None,
        vtt=output_dir / f"{stem}.transcript.vtt" if vtt else None,
    )
