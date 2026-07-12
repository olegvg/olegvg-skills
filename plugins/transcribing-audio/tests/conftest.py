from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

import pytest


@pytest.fixture
def generated_wav(tmp_path: Path) -> tuple[Path, Path]:
    """Generate deterministic tone and silence fixtures without committing audio."""
    tone = tmp_path / "tone с пробелом.wav"
    silence = tmp_path / "silence.wav"
    for target, amplitude in ((tone, 8_000), (silence, 0)):
        with wave.open(str(target), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16_000)
            frames = b"".join(
                struct.pack("<h", int(amplitude * math.sin(index / 20))) for index in range(16_000)
            )
            output.writeframes(frames)
    return tone, silence
