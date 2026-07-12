#!/usr/bin/env python3
"""Bootstrap the isolated audio-transcription runtime."""

from __future__ import annotations

import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = PLUGIN_ROOT / "scripts"

if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from audio_transcriber.bootstrap import launch  # noqa: E402


if __name__ == "__main__":
    launch(sys.argv[1:])
