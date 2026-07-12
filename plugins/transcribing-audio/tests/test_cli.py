from __future__ import annotations

import argparse
from io import StringIO
from pathlib import Path

import pytest

from audio_transcriber.cli import ConsentRequiredError, build_parser, resolve_interaction
from audio_transcriber.models import Mode


class _TTY(StringIO):
    def isatty(self) -> bool:
        return True


class _Pipe(StringIO):
    def isatty(self) -> bool:
        return False


def _args(*argv: str) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def test_parser_accepts_the_documented_mode_and_speaker_options() -> None:
    args = _args(
        "recording.wav",
        "--mode",
        "local",
        "--min-speakers",
        "2",
        "--max-speakers",
        "4",
        "--speaker-names",
        "SPEAKER_00=Alice, SPEAKER_01=Bob",
    )

    assert args.input_path == Path("recording.wav")
    assert args.mode is Mode.LOCAL
    assert (args.min_speakers, args.max_speakers) == (2, 4)
    with pytest.raises(SystemExit):
        _args("recording.wav", "--speakers", "2", "--min-speakers", "1")
    with pytest.raises(SystemExit):
        _args("recording.wav", "--speakers", "2", "--max-speakers", "3")


def test_tty_prompts_even_when_cli_values_supply_defaults() -> None:
    args = _args("cli.wav", "--mode", "openai", "--speakers", "2", "--allow-cloud-upload")
    stdout = StringIO()

    interaction = resolve_interaction(
        args,
        stdin=_TTY("\n\n\nyes\n"),
        stdout=stdout,
    )

    assert interaction.input_path == Path("cli.wav")
    assert interaction.mode is Mode.OPENAI
    assert interaction.speakers == 2
    assert interaction.consent is not None and interaction.consent.granted
    assert interaction.consent.interactive
    assert "OpenAI" in stdout.getvalue()


def test_non_tty_requires_mode_input_and_openai_consent() -> None:
    with pytest.raises(ValueError, match="input path"):
        resolve_interaction(_args(), stdin=_Pipe(), stdout=StringIO())
    with pytest.raises(ValueError, match="--mode"):
        resolve_interaction(_args("recording.wav"), stdin=_Pipe(), stdout=StringIO())
    with pytest.raises(ConsentRequiredError):
        resolve_interaction(
            _args("recording.wav", "--mode", "openai"), stdin=_Pipe(), stdout=StringIO()
        )

    interaction = resolve_interaction(
        _args("recording.wav", "--mode", "openai", "--allow-cloud-upload"),
        stdin=_Pipe(),
        stdout=StringIO(),
    )
    assert interaction.consent is not None and not interaction.consent.interactive


def test_interactive_openai_denial_cannot_be_bypassed_by_a_flag() -> None:
    with pytest.raises(ConsentRequiredError):
        resolve_interaction(
            _args("recording.wav", "--mode", "openai", "--allow-cloud-upload"),
            stdin=_TTY("\n\n\nn\n"),
            stdout=StringIO(),
        )


def test_interaction_validates_tty_speaker_ranges_and_missing_prompts() -> None:
    interaction = resolve_interaction(
        _args("recording.wav", "--mode", "local"),
        stdin=_TTY("\n\n2-4\n"),
        stdout=StringIO(),
    )
    assert (interaction.speakers, interaction.min_speakers, interaction.max_speakers) == (
        None,
        2,
        4,
    )

    with pytest.raises(ValueError, match="input audio path"):
        resolve_interaction(_args(), stdin=_TTY("\n"), stdout=StringIO())
    with pytest.raises(ValueError, match="mode must be"):
        resolve_interaction(_args("recording.wav"), stdin=_TTY("\ninvalid\n"), stdout=StringIO())
    with pytest.raises(ValueError, match="speaker policy"):
        resolve_interaction(
            _args("recording.wav", "--mode", "local"),
            stdin=_TTY("\n\n2-\n"),
            stdout=StringIO(),
        )


def test_non_tty_rejects_invalid_local_cloud_and_speaker_values() -> None:
    with pytest.raises(ValueError, match="only valid with --mode openai"):
        resolve_interaction(
            _args("recording.wav", "--mode", "local", "--allow-cloud-upload"),
            stdin=_Pipe(),
            stdout=StringIO(),
        )
    with pytest.raises(ValueError, match="positive"):
        resolve_interaction(
            _args("recording.wav", "--mode", "local", "--min-speakers", "-1"),
            stdin=_Pipe(),
            stdout=StringIO(),
        )
    with pytest.raises(ValueError, match="minimum speakers"):
        resolve_interaction(
            _args("recording.wav", "--mode", "local", "--min-speakers", "4", "--max-speakers", "2"),
            stdin=_Pipe(),
            stdout=StringIO(),
        )
