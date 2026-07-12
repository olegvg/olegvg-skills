"""Stdlib-only dependency boundaries for runtime adapters."""

from __future__ import annotations

import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol

from .models import ASRChunkResult, ASROptions, AudioChunk, DiarizationTurn, SpeakerCount


class CommandRunner(Protocol):
    """Runs a command from an argument vector without involving a shell."""

    def __call__(
        self,
        argv: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        timeout_s: float = 10.0,
    ) -> subprocess.CompletedProcess[str]: ...


class ASRBackend(Protocol):
    """Produces timestamped transcription data for one normalized audio chunk."""

    def transcribe(self, chunk: AudioChunk, options: ASROptions) -> ASRChunkResult: ...

    def health_check(self, model: str) -> None: ...


class DiarizationBackend(Protocol):
    """Produces raw local-speaker turns for a normalized recording."""

    def diarize(self, audio_path: Path, speakers: SpeakerCount) -> tuple[DiarizationTurn, ...]: ...

    def health_check(self) -> None: ...
