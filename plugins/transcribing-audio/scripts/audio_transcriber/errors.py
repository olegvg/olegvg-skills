"""Safe, domain-specific errors that never expose credentials."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import AbstractSet

from .models import StageName

_ENV_SECRET_PATTERN = re.compile(
    r"(?i)\b(?:OPENAI_API_KEY|HF_TOKEN)\b\s*(?:=|:)\s*(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)


def redact_text(text: str, secrets: AbstractSet[str]) -> str:
    """Remove explicit secret values and supported credential assignments."""
    redacted = text
    for secret in sorted((value for value in secrets if value), key=len, reverse=True):
        redacted = redacted.replace(secret, "[REDACTED]")
    return _ENV_SECRET_PATTERN.sub("[REDACTED]", redacted)


@dataclass(slots=True)
class SafeError(Exception):
    stage: StageName
    message: str = field(repr=False)
    start_s: float | None = None
    end_s: float | None = None
    backend: str | None = None
    recovery_hint: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not self.message:
            raise ValueError("message must not be empty")
        if self.start_s is not None and self.end_s is not None and self.end_s < self.start_s:
            raise ValueError("end timestamp must not precede start timestamp")

    def render(self, secrets: AbstractSet[str]) -> str:
        pieces = [self.stage.value, redact_text(self.message, secrets)]
        if self.start_s is not None and self.end_s is not None:
            pieces.append(f"{self.start_s:.3f}s-{self.end_s:.3f}s")
        if self.backend:
            pieces.append(f"backend={self.backend}")
        if self.recovery_hint:
            pieces.append(redact_text(self.recovery_hint, secrets))
        return " | ".join(pieces)
