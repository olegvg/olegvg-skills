"""Safe interactive and non-interactive command boundary for transcription."""

from __future__ import annotations

import argparse
import importlib
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from openai import OpenAI

from .asr_local import FasterWhisperASR, MlxASR
from .asr_openai import OpenAIASR
from .bootstrap import RuntimeHandle, ensure_runtime, reexec_after_component_failure
from .config import ConfigOverrides, ResolvedConfig, resolve_config
from .diarization import PyannoteDiarizer
from .errors import SafeError, redact_text
from .models import BackendFamily, Mode, RuntimeComponent, StageName, UploadConsent
from .pipeline import (
    PipelineDependencies,
    PipelineRunner,
    RuntimeRecoveryRequired,
    publish_outputs,
)
from .quality import UnresolvedQualityError


class ConsentRequiredError(ValueError):
    """The explicit cloud-upload consent contract was not met."""


class _SpeakerCountAction(argparse.Action):
    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: object,
        option_string: str | None = None,
    ) -> None:
        del option_string
        if self.dest == "speakers" and getattr(namespace, "max_speakers", None) is not None:
            parser.error("--speakers cannot be combined with --max-speakers")
        if self.dest == "max_speakers" and getattr(namespace, "speakers", None) is not None:
            parser.error("--speakers cannot be combined with --max-speakers")
        setattr(namespace, self.dest, values)


@dataclass(frozen=True, slots=True)
class InteractionResult:
    input_path: Path
    mode: Mode
    consent: UploadConsent | None
    interactive: bool
    speakers: int | None
    min_speakers: int | None
    max_speakers: int | None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Transcribe audio with local diarization.")
    parser.add_argument("input_path", nargs="?", type=Path, metavar="INPUT")
    parser.add_argument("--mode", choices=tuple(Mode), type=Mode)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--language")
    parser.add_argument("--local-model")
    parser.add_argument("--openai-model")
    speakers = parser.add_mutually_exclusive_group()
    speakers.add_argument("--speakers", type=int, action=_SpeakerCountAction)
    speakers.add_argument("--min-speakers", type=int)
    parser.add_argument("--max-speakers", type=int, action=_SpeakerCountAction)
    parser.add_argument("--speaker-names")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--resume", action="store_true", default=None)
    parser.add_argument("--overwrite", action="store_true", default=None)
    parser.add_argument("--reprobe", action="store_true", default=False)
    parser.add_argument("--srt", action="store_true", default=None)
    parser.add_argument("--vtt", action="store_true", default=None)
    parser.add_argument("--allow-cloud-upload", action="store_true", default=False)
    parser.add_argument("--debug", action="store_true", default=False)
    return parser


def _read_prompt(stdin: TextIO, stdout: TextIO, message: str) -> str:
    stdout.write(message)
    stdout.flush()
    value = stdin.readline()
    return value.strip() if value else ""


def _speaker_prompt(value: str) -> tuple[int | None, int | None, int | None]:
    if not value or value.casefold() in {"auto", "a"}:
        return None, None, None
    if value.isdecimal() and int(value) > 0:
        return int(value), None, None
    minimum, separator, maximum = value.partition("-")
    if separator and (
        not minimum or not maximum or not minimum.isdecimal() or not maximum.isdecimal()
    ):
        raise ValueError("speaker policy must be auto, a positive count, or MIN-MAX")
    if separator:
        low, high = int(minimum), int(maximum)
        if low <= 0 or high <= 0 or low > high:
            raise ValueError("speaker range is invalid")
        return None, low, high
    raise ValueError("speaker policy must be auto, a positive count, or MIN-MAX")


def _validate_speaker_values(
    speakers: int | None, minimum: int | None, maximum: int | None
) -> tuple[int | None, int | None, int | None]:
    if speakers is not None and (minimum is not None or maximum is not None):
        raise ValueError("--speakers cannot be combined with a speaker range")
    for value in (speakers, minimum, maximum):
        if value is not None and value <= 0:
            raise ValueError("speaker counts must be positive")
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ValueError("minimum speakers cannot exceed maximum speakers")
    return speakers, minimum, maximum


def resolve_interaction(
    args: argparse.Namespace,
    *,
    stdin: TextIO,
    stdout: TextIO,
) -> InteractionResult:
    """Resolve a one-run interaction without retaining any prompt response."""
    interactive = stdin.isatty()
    if not interactive:
        if args.input_path is None:
            raise ValueError("an input path is required when stdin is not a TTY")
        if args.mode is None:
            raise ValueError("--mode is required when stdin is not a TTY")
        if args.mode is Mode.LOCAL and args.allow_cloud_upload:
            raise ValueError("--allow-cloud-upload is only valid with --mode openai")
        speakers = _validate_speaker_values(args.speakers, args.min_speakers, args.max_speakers)
        consent = None
        if args.mode is Mode.OPENAI:
            if not args.allow_cloud_upload:
                raise ConsentRequiredError(
                    "--allow-cloud-upload is required for non-interactive OpenAI mode"
                )
            consent = UploadConsent(provider="openai", granted=True, interactive=False)
        return InteractionResult(args.input_path, args.mode, consent, False, *speakers)

    input_default = str(args.input_path) if args.input_path is not None else ""
    input_value = (
        _read_prompt(stdin, stdout, f"Audio input path [{input_default}]: ") or input_default
    )
    if not input_value:
        raise ValueError("an input audio path is required")
    mode_default = args.mode.value if args.mode is not None else ""
    mode_value = (
        _read_prompt(stdin, stdout, f"ASR mode (local/openai) [{mode_default}]: ") or mode_default
    )
    try:
        mode = Mode(mode_value)
    except ValueError as exc:
        raise ValueError("mode must be local or openai") from exc
    if args.speakers is not None:
        speaker_default = str(args.speakers)
    elif args.min_speakers is not None or args.max_speakers is not None:
        speaker_default = f"{args.min_speakers or ''}-{args.max_speakers or ''}"
    else:
        speaker_default = "auto"
    speaker_value = (
        _read_prompt(stdin, stdout, f"Speaker policy (auto, N, or MIN-MAX) [{speaker_default}]: ")
        or speaker_default
    )
    speakers = _speaker_prompt(speaker_value)
    if mode is Mode.LOCAL:
        if args.allow_cloud_upload:
            raise ValueError("--allow-cloud-upload is only valid with --mode openai")
        return InteractionResult(Path(input_value), mode, None, True, *speakers)
    confirmation = _read_prompt(
        stdin,
        stdout,
        "OpenAI mode uploads audio chunks to OpenAI for transcription. Continue? [y/N]: ",
    )
    if confirmation.casefold() not in {"y", "yes"}:
        raise ConsentRequiredError("OpenAI upload consent was denied")
    return InteractionResult(
        Path(input_value),
        mode,
        UploadConsent(provider="openai", granted=True, interactive=True),
        True,
        *speakers,
    )


def _command_runner(
    argv: Sequence[str], *, env: Mapping[str, str] | None = None, timeout_s: float = 10.0
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        check=False,
        shell=False,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout_s,
    )


def _mlx_transcriber() -> Callable[..., object]:
    module = importlib.import_module("mlx_whisper")
    transcribe = getattr(module, "transcribe", None)
    if not callable(transcribe):
        raise RuntimeError("mlx-whisper does not expose transcribe")
    return transcribe


def _faster_whisper_model(model: str, device: str, compute_type: str) -> object:
    module = importlib.import_module("faster_whisper")
    model_type = getattr(module, "WhisperModel", None)
    if not callable(model_type):
        raise RuntimeError("faster-whisper does not expose WhisperModel")
    return model_type(model, device=device, compute_type=compute_type)


def _asr_factory(
    config: ResolvedConfig, runtime: RuntimeHandle, consent: UploadConsent | None
) -> MlxASR | FasterWhisperASR | OpenAIASR:
    if config.mode is Mode.OPENAI:
        if consent is None:
            raise ConsentRequiredError("OpenAI mode requires explicit upload consent")
        return OpenAIASR(
            OpenAI(api_key=config.credentials.openai_api_key),
            api_key=config.credentials.openai_api_key,
            consent=consent,
        )
    if runtime.backend is BackendFamily.MLX:
        return MlxASR(_mlx_transcriber)
    return FasterWhisperASR(
        _faster_whisper_model,
        runtime.backend,
        cuda_compute_type="float16",
    )


def _diarizer_factory(
    config: ResolvedConfig, runtime: RuntimeHandle, duration_s: float
) -> PyannoteDiarizer:
    return PyannoteDiarizer(
        model_id=config.diarization_model,
        revision=config.diarization_revision,
        compute_device=runtime.compute_device,
        credentials=config.credentials,
        duration_s=duration_s,
    )


def _default_dependencies() -> PipelineDependencies:
    return PipelineDependencies(
        command_runner=_command_runner,
        which=shutil.which,
        asr_factory=_asr_factory,
        diarizer_factory=_diarizer_factory,
        clock=lambda: datetime.now(UTC),
        publisher=publish_outputs,
    )


def _runtime_component(
    recovery: RuntimeRecoveryRequired, runtime: RuntimeHandle
) -> RuntimeComponent:
    if recovery.component == "diarization":
        return {
            "mps": RuntimeComponent.DIARIZATION_MPS,
            "cuda": RuntimeComponent.DIARIZATION_CUDA,
            "cpu": RuntimeComponent.DIARIZATION_CPU,
        }[runtime.compute_device.value]
    return {
        BackendFamily.MLX: RuntimeComponent.ASR_MLX,
        BackendFamily.CUDA: RuntimeComponent.ASR_CUDA,
        BackendFamily.CPU: RuntimeComponent.ASR_CPU,
    }[runtime.backend]


def _safe_error_message(error: BaseException, config: ResolvedConfig | None = None) -> str:
    secrets: set[str] = set()
    if config is not None:
        secrets.update(
            value
            for value in (config.credentials.hf_token, config.credentials.openai_api_key)
            if value
        )
    if isinstance(error, SafeError):
        return error.render(secrets)
    return redact_text(str(error), secrets)


def main(
    argv: Sequence[str] | None = None,
    *,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    config: ResolvedConfig | None = None
    try:
        args = parser.parse_args(arguments)
        interaction = resolve_interaction(
            args, stdin=stdin, stdout=stderr if stdin.isatty() else stdout
        )
        overrides = ConfigOverrides(
            input_path=interaction.input_path,
            mode=interaction.mode,
            env_file=args.env_file,
            output_dir=args.output_dir,
            local_model=args.local_model,
            openai_model=args.openai_model,
            language=args.language,
            speakers=interaction.speakers,
            min_speakers=interaction.min_speakers,
            max_speakers=interaction.max_speakers,
            speaker_names=args.speaker_names,
            resume=args.resume,
            overwrite=args.overwrite,
            render_srt=args.srt,
            render_vtt=args.vtt,
        )
        plugin_root = Path(__file__).resolve().parents[2]
        config = resolve_config(overrides, plugin_root)
        runtime = ensure_runtime(plugin_root, reprobe=args.reprobe, input_path=config.input_path)
        result = PipelineRunner(
            runtime,
            _default_dependencies(),
            consent=interaction.consent,
        ).run(config)
        stdout.write(f"Transcript written to {result.json}\n")
        return 0
    except KeyboardInterrupt:
        stderr.write("Transcription interrupted. Completed stages were preserved.\n")
        return 130
    except ConsentRequiredError as exc:
        stderr.write(f"{_safe_error_message(exc, config)}\n")
        return 4
    except UnresolvedQualityError as exc:
        stderr.write(f"{_safe_error_message(exc, config)}\n")
        return 6
    except RuntimeRecoveryRequired as exc:
        if config is None:
            stderr.write(_safe_error_message(exc.error) + "\n")
            return 5
        runtime = ensure_runtime(Path(__file__).resolve().parents[2], reprobe=False)
        reexec_after_component_failure(
            runtime, _runtime_component(exc, runtime), exc.error.message, arguments
        )
    except SafeError as exc:
        stderr.write(_safe_error_message(exc, config) + "\n")
        return 5 if exc.stage is not StageName.CONFIGURE else 3
    except (OSError, ValueError) as exc:
        stderr.write(_safe_error_message(exc, config) + "\n")
        return 2
    except Exception as exc:
        stderr.write(_safe_error_message(exc, config) + "\n")
        return 5
    return 5


if __name__ == "__main__":
    raise SystemExit(main())
