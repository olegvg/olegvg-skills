# Transcribing Audio Plugin Development Plan

> Historical implementation record. It was created in `psy_bot` and moved to this repository on 2026-07-12; source-repository references below describe that original delivery context.

Source specification: [Audio Transcription and Diarization Skill Design](../../specs/2026-07-10-transcribing-audio-skill-design.md)

## Scope

Build a repository-local Codex plugin at `plugins/transcribing-audio/`. The source design remains authoritative for transcription behavior, privacy, runtime isolation, resumability, diarization, quality gates, and outputs; this plan intentionally supersedes only its packaging decision. The plugin owns one discoverable skill under `skills/transcribing-audio/` and the executable runtime under top-level `scripts/`.

The plugin is operationally isolated from `psy_bot`: it must not import project packages, reuse the project virtual environment, read application settings, or change chatbot runtime behavior. Repository integration is limited to the plugin source plus the repo marketplace entry at `.agents/plugins/marketplace.json`.

## Development Stages

| Stage | Deliverable | Plan | Verification checklist |
| --- | --- | --- | --- |
| 1 | Dependency spike, plugin/marketplace scaffold, script runtime skeleton, typed contracts, safe configuration, platform probing, cached runtime | [Stage 1 plan](plan-transcribing-audio-plugin-stage-1-foundation.md) | [Stage 1 checklist](checklist-transcribing-audio-plugin-stage-1-foundation.md) |
| 2 | Resumable run state, media normalization, local/OpenAI ASR, quality gates and retry | [Stage 2 plan](plan-transcribing-audio-plugin-stage-2-asr.md) | [Stage 2 checklist](checklist-transcribing-audio-plugin-stage-2-asr.md) |
| 3 | Local diarization, deterministic alignment, canonical JSON and derived renderers | [Stage 3 plan](plan-transcribing-audio-plugin-stage-3-diarization-output.md) | [Stage 3 checklist](checklist-transcribing-audio-plugin-stage-3-diarization-output.md) |
| 4 | Interactive/non-interactive CLI, consent, pipeline orchestration, resume and publishing | [Stage 4 plan](plan-transcribing-audio-plugin-stage-4-cli-integration.md) | [Stage 4 checklist](checklist-transcribing-audio-plugin-stage-4-cli-integration.md) |
| 5 | Skill documentation, plugin manifest/marketplace validation, install/reinstall checks, coverage, smoke tests and forward tests | [Stage 5 plan](plan-transcribing-audio-plugin-stage-5-validation.md) | [Stage 5 checklist](checklist-transcribing-audio-plugin-stage-5-validation.md) |

Execute stages in order. Each stage must be reviewed and its checklist completed before starting the next stage. When implementation begins, use `superpowers:subagent-driven-development` or `superpowers:executing-plans` and preserve RED-GREEN-REFACTOR evidence in the corresponding checklist.

## Canonical File Map

```text
plugins/transcribing-audio/
├── .codex-plugin/
│   └── plugin.json                   # Required plugin manifest; name matches folder
├── pyproject.toml                   # Standalone runtime/test dependencies
├── uv.lock                          # Exact reproducible dependency resolution
├── skills/
│   └── transcribing-audio/
│       ├── SKILL.md                 # Concise workflow and reference routing
│       ├── agents/
│       │   └── openai.yaml          # Skill metadata and default prompt
│       └── references/
│           ├── runtime-and-backends.md
│           ├── local-asr.md
│           ├── openai-asr.md
│           ├── diarization-and-alignment.md
│           ├── quality-and-recovery.md
│           └── output-schema.md
├── scripts/
│   ├── transcribe_audio.py          # Stdlib-only bootstrap launcher
│   └── audio_transcriber/
│       ├── __init__.py
│       ├── errors.py                # Safe domain exceptions and redaction
│       ├── constants.py             # Machine-readable versions, flags and defaults
│       ├── interfaces.py            # Stdlib-only dependency Protocols
│       ├── models.py                # Immutable cross-stage data contracts
│       ├── bootstrap.py             # Probe, fingerprint, venv provision and re-exec
│       ├── cli.py                   # Argument parsing and prompts
│       ├── pipeline.py              # Stage orchestration and final publishing
│       ├── config.py                # Precedence, env selection and secret loading
│       ├── state.py                 # Run identity and atomic stage manifests
│       ├── audio.py                 # ffprobe, normalization and chunk extraction
│       ├── asr.py                   # Backend-neutral chunk merge and deduplication
│       ├── asr_local.py             # MLX/faster-whisper adapters
│       ├── asr_openai.py            # OpenAI timestamped transcription adapter
│       ├── diarization.py           # Local pyannote execution and validation
│       ├── alignment.py             # Word-to-speaker assignment and turn merging
│       ├── quality.py               # ASR gates and bounded recovery
│       └── renderers.py             # Canonical JSON, TXT, SRT and VTT
└── tests/
    ├── conftest.py
    ├── fixtures/
    │   ├── asr/
    │   └── diarization/
    ├── test_layout.py
    ├── test_models.py
    ├── test_config.py
    ├── test_bootstrap.py
    ├── test_state.py
    ├── test_audio.py
    ├── test_asr.py
    ├── test_asr_local.py
    ├── test_asr_openai.py
    ├── test_quality.py
    ├── test_diarization.py
    ├── test_alignment.py
    ├── test_renderers.py
    ├── test_cli.py
    ├── test_pipeline.py
    ├── test_pipeline_integration.py
    └── test_skill_contract.py
```

Repository marketplace integration is outside the plugin archive:

```text
.agents/plugins/marketplace.json    # Entry name/source/policy/category for transcribing-audio
```

`errors.py`, `interfaces.py`, `models.py`, `asr.py`, and `pipeline.py` are deliberate additions to the design's illustrative layout. They prevent unrelated modules from duplicating safety behavior, defining incompatible payloads, or mixing CLI interaction with orchestration.

## Cross-Stage Contracts

- All persisted domain objects are immutable `@dataclass(frozen=True, slots=True)` values with explicit `to_dict`/`from_dict` validation.
- `.codex-plugin/plugin.json`, the outer directory, and the marketplace entry all use the normalized name `transcribing-audio`.
- The manifest declares `skills: "./skills/"`; it does not declare apps, MCP servers, hooks, or assets that are not present.
- The embedded skill resolves the launcher relative to its own installed location (`../../scripts/transcribe_audio.py`), never from repository cwd or a hardcoded checkout path.
- `scripts/transcribe_audio.py` and the part of `bootstrap.py` imported before re-exec use only the Python standard library.
- The plugin owns one reusable environment at `plugins/transcribing-audio/.venv/`. Runtime fingerprints never create another environment; they only invalidate safe runtime-state records under the private `/tmp` root. The environment is ignored by Git.
- The current runtime index avoids re-running MLX/CUDA probes when the cheap base fingerprint is unchanged.
- Local ASR backend (`mlx`, `cuda`, `cpu`) and pyannote compute device (`mps`, `cuda`, `cpu`) are separate values.
- Runtime recovery persists failed backend/device exclusions under the private `/tmp` runtime root and permits only one re-probe/re-exec.
- Run stages publish only same-directory temporary files through `os.replace` after validation and SHA-256 recording.
- ASR and diarization depend on Protocol-based adapters so unit/integration tests never require network access or model downloads.
- OpenAI is an ASR provider only. Diarization always runs locally through pyannote.
- Word timestamps are mandatory in canonical JSON; per-word confidence is nullable.
- Canonical JSON is the sole source for TXT/SRT/VTT. No renderer reads backend-native data.
- No secret-bearing object is serializable, printable through `repr`, or passed in a subprocess argument.

## Shared Verification Commands

Run from the repository root:

```bash
export PLUGIN_ROOT="$PWD/plugins/transcribing-audio"
export UV_PROJECT_ENVIRONMENT="$PLUGIN_ROOT/.venv"
uv sync --project "$PLUGIN_ROOT" --frozen --all-extras --group dev
uv run --project "$PLUGIN_ROOT" pytest "$PLUGIN_ROOT/tests" -q
uv run --project "$PLUGIN_ROOT" pytest "$PLUGIN_ROOT/tests" --cov="$PLUGIN_ROOT/scripts/audio_transcriber" --cov-report=term-missing --cov-fail-under=80
uv run --project "$PLUGIN_ROOT" pyright --project "$PLUGIN_ROOT/pyproject.toml"
uvx ruff check "$PLUGIN_ROOT"
uvx ruff format --check "$PLUGIN_ROOT"
```

The repository-wide `make test` and `uv run pyright` commands are final regression gates. The explicit pyright project above is the independent plugin-runtime type-check gate. Stage 5 additionally runs the canonical plugin validator and validates the nested skill.

## Current Primary References

Recheck these at implementation time because provider and library APIs change:

- uv project environments and frozen sync: https://docs.astral.sh/uv/concepts/projects/config/ and https://docs.astral.sh/uv/concepts/projects/sync/
- pyannote local community pipeline: https://github.com/pyannote/pyannote-audio
- faster-whisper word timestamps: https://github.com/SYSTRAN/faster-whisper
- MLX Whisper word timestamps: https://github.com/ml-explore/mlx-examples/tree/main/whisper
- OpenAI transcription API: https://platform.openai.com/docs/api-reference/audio/createTranscription
