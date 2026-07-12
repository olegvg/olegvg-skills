# Transcribing Audio Plugin Stage 1: Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the dependency/platform contract, then create a valid repository-local plugin with a nested discovery skill, script-based runtime, immutable contracts, secret-safe configuration, deterministic platform selection, and one reusable plugin-local virtual environment.

**Architecture:** The plugin root contains the required `.codex-plugin/plugin.json`, a nested `skills/transcribing-audio/` component for discovery and progressive disclosure, and executable implementation under top-level `scripts/`. A stdlib-only launcher computes a cheap base fingerprint, reuses a validated runtime index when possible, and performs an expensive MLX/CUDA/CPU probe only when required. Dependencies are locked by uv only after a compatibility spike, and shared values cross script-module boundaries through immutable typed models.

**Tech Stack:** Python selected by the compatibility spike (target 3.13), uv, pytest, pytest-cov, pyright, ruff, python-dotenv, OpenAI Python SDK, pyannote.audio, faster-whisper, mlx-whisper.

## Global Constraints

- Create the plugin only under `plugins/transcribing-audio/`; add only its repo-local marketplace entry outside that tree at `.agents/plugins/marketplace.json`.
- Keep the executable Python implementation in plugin-root `scripts/`; the nested skill routes agents to those scripts and does not duplicate implementation logic.
- Keep `.codex-plugin/plugin.json`, the plugin folder, nested skill, and marketplace entry consistently named `transcribing-audio`.
- Preserve an existing marketplace name/interface, unrelated entries and render order; append the new entry. Do not use `--marketplace-name` or `--force` unless a documented collision or intentional replacement requires it.
- Do not import `psy_bot` or use the repository's application configuration.
- Keep exactly one runtime environment at `plugins/transcribing-audio/.venv/`; it is Git-ignored and reused for every platform/backend choice. Runtime fingerprints must not create variant virtual environments. Keep mutable runtime state under the per-user top-level root `/tmp/psy-audio-transcriber-<uid>/` with mode `0700` and no-follow path validation. A shared ordinary-user-owned parent is forbidden because it is not safe on multi-user hosts.
- Keep model downloads in their normal persistent platform caches, never under `/tmp`.
- Support macOS Apple Silicon MLX first, then NVIDIA CUDA, then CPU fallback; do not claim Windows support in version 1.
- A normal cached launch validates state and executable presence without a full hardware probe.
- Model ASR backend separately from the pyannote compute device.
- Read only `OPENAI_API_KEY` and `HF_TOKEN` from dotenv sources; never log or persist their values.
- Use immutable objects, per-run locks, and atomic writes.
- Use TDD and maintain at least 80% executable-runtime coverage.
- Do not add README, installation guide, changelog, app manifest, MCP manifest, hooks, or placeholder assets inside the plugin.

---

### Task 1: Run the dependency and provider compatibility spike

**Files:**
- Modify during execution: `checklist-transcribing-audio-plugin-stage-1-foundation.md`

**Interfaces:**
- Consumes: current primary documentation for uv, Python, PyTorch/pyannote, MLX Whisper, faster-whisper and OpenAI Audio Transcriptions.
- Produces: an exact compatibility decision recorded in the Stage 1 checklist before `pyproject.toml` or `uv.lock` is created.

- [ ] **Step 1: Resolve current dependency and provider contracts**

Use Context7 for uv, pyannote.audio and faster-whisper; official MLX GitHub documentation for mlx-whisper; and `openai-docs` for the Audio Transcriptions API. Record:

- selected Python minor, preferring 3.13 if every backend resolves;
- package names and compatible current versions;
- pyannote model ID and pinned revision if the API supports it;
- OpenAI model/response format that actually returns word timestamps;
- current documented upload limit, or a conservative 24,000,000-byte ceiling if no limit is published;
- required OS/architecture markers and external ffmpeg/NVIDIA prerequisites.

- [ ] **Step 2: Prove one lock resolves for all supported platforms**

After Task 2 creates the standalone project, resolve base, `mlx`, and `faster` extras into its one universal `uv.lock`. Sync all extras only into `plugins/transcribing-audio/.venv/`; do not create a dependency-spike environment or any runtime-fingerprint-specific environments. Record the command output and selected versions in the checklist.

Expected: one lock can represent macOS arm64 MLX and macOS/Linux faster-whisper environments. If Python 3.13 cannot resolve, stop and amend the design before proceeding; do not silently lower the version.

- [ ] **Step 3: Capture the RED plugin baseline**

Select one readable, non-sensitive external recording and known exact speaker count for both baseline and Stage 5 forward tests:

```bash
export TRANSCRIBER_FORWARD_AUDIO="/absolute/private/path/to/multi-speaker-recording"
export TRANSCRIBER_FORWARD_SPEAKERS="2"
```

In a fresh context where the new plugin is not installed, issue this natural prompt with the variables expanded to their actual values:

```text
Transcribe <TRANSCRIBER_FORWARD_AUDIO> locally into word-timestamped JSON and speaker-labelled text for exactly <TRANSCRIBER_FORWARD_SPEAKERS> speakers. Make interrupted work resumable.
```

Record the baseline's exact commands, created artifacts, failures, and whether it omits consent, timestamps, diarization constraints, repetition recovery, isolated dependencies, or resume. Preserve the same external recording/count for Stage 5; do not commit audio, transcripts, or credentials.

---

### Task 2: Scaffold the standalone plugin, nested skill, marketplace entry, and script runtime

**Files:**
- Create: `plugins/transcribing-audio/.codex-plugin/plugin.json`
- Create: `plugins/transcribing-audio/skills/transcribing-audio/SKILL.md`
- Create: `plugins/transcribing-audio/skills/transcribing-audio/agents/openai.yaml`
- Create or modify: `.agents/plugins/marketplace.json`
- Create: `plugins/transcribing-audio/pyproject.toml`
- Create: `plugins/transcribing-audio/uv.lock`
- Create: `plugins/transcribing-audio/scripts/transcribe_audio.py`
- Create: `plugins/transcribing-audio/scripts/audio_transcriber/__init__.py`
- Create: `plugins/transcribing-audio/scripts/audio_transcriber/constants.py`
- Create: `plugins/transcribing-audio/scripts/audio_transcriber/interfaces.py`
- Create: `plugins/transcribing-audio/tests/test_layout.py`

**Interfaces:**
- Consumes: compatibility decision from Task 1.
- Produces: importable package `audio_transcriber` and executable launcher path `plugins/transcribing-audio/scripts/transcribe_audio.py`.

- [ ] **Step 1: Initialize the plugin with the canonical plugin scaffold**

Run:

```bash
python3 "$HOME/.codex/skills/.system/plugin-creator/scripts/create_basic_plugin.py" transcribing-audio \
  --path "$PWD/plugins" \
  --marketplace-path "$PWD/.agents/plugins/marketplace.json" \
  --with-skills \
  --with-scripts \
  --with-marketplace

uv run --isolated --no-project --with pyyaml "$HOME/.codex/skills/.system/skill-creator/scripts/init_skill.py" transcribing-audio \
  --path plugins/transcribing-audio/skills \
  --resources references \
  --interface display_name="Audio Transcription" \
  --interface short_description="Transcribe and diarize speaker-labelled audio" \
  --interface default_prompt='Use $transcribing-audio to transcribe this recording with speaker labels.'
```

Expected: the outer folder name and manifest name are both `transcribing-audio`; `.codex-plugin/plugin.json` exists; the manifest declares `skills: "./skills/"` and no absent apps/MCP/hooks/assets; the repo marketplace entry uses source path `./plugins/transcribing-audio` and includes installation/authentication policy plus category; `skills/transcribing-audio/` contains `SKILL.md` and `agents/openai.yaml`; plugin-root `scripts/` exists. Delete only generator examples/placeholders, never required scaffold files.

- [ ] **Step 2: Write the failing layout test**

```python
import json
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = PLUGIN_ROOT / "skills" / "transcribing-audio"
MARKETPLACE_PATH = PLUGIN_ROOT.parents[1] / ".agents" / "plugins" / "marketplace.json"


def test_plugin_has_required_top_level_artifacts() -> None:
    required = {".codex-plugin", "skills", "pyproject.toml", "scripts", "tests", "uv.lock"}
    assert required <= {path.name for path in PLUGIN_ROOT.iterdir()}
    assert not (PLUGIN_ROOT / "README.md").exists()


def test_plugin_contains_discoverable_skill() -> None:
    assert (SKILL_ROOT / "SKILL.md").is_file()
    assert (SKILL_ROOT / "agents" / "openai.yaml").is_file()


def test_manifest_and_marketplace_use_canonical_name() -> None:
    manifest = json.loads((PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text())
    assert manifest["name"] == PLUGIN_ROOT.name == "transcribing-audio"
    assert manifest["skills"] == "./skills/"
    assert "apps" not in manifest and "mcpServers" not in manifest and "hooks" not in manifest

    marketplace = json.loads(MARKETPLACE_PATH.read_text())
    entry = next(item for item in marketplace["plugins"] if item["name"] == "transcribing-audio")
    assert entry["source"] == {"source": "local", "path": "./plugins/transcribing-audio"}
    assert entry["policy"] == {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}
    assert entry["category"]


def test_launcher_imports_only_stdlib_before_bootstrap() -> None:
    source = (PLUGIN_ROOT / "scripts" / "transcribe_audio.py").read_text()
    forbidden = ("openai", "dotenv", "pyannote", "torch", "faster_whisper", "mlx_whisper")
    assert all(name not in source for name in forbidden)
```

- [ ] **Step 3: Run the layout test and verify RED**

Run:

```bash
uv run --isolated --no-project --with pytest pytest plugins/transcribing-audio/tests/test_layout.py -q
```

Expected: FAIL only on planned layout assertions; this command must not discover or resolve the root `psy_bot` project.

- [ ] **Step 4: Define and lock the isolated project**

Write `pyproject.toml` with the package names and platform markers approved in Task 1. Keep direct requirements readable and let `uv.lock` carry the exact resolution:

```toml
[project]
name = "transcribing-audio-runtime"
version = "0.1.0"
requires-python = ">=3.13,<3.14"
dependencies = ["openai", "pyannote.audio", "python-dotenv", "torch"]

[project.optional-dependencies]
faster = ["faster-whisper"]
mlx = ["mlx-whisper; sys_platform == 'darwin' and platform_machine == 'arm64'"]

[dependency-groups]
dev = ["pyright", "pytest", "pytest-cov", "pytest-mock", "ruff"]

[tool.pytest.ini_options]
addopts = "-ra --strict-markers"
testpaths = ["tests"]
pythonpath = ["scripts"]
markers = [
  "network: requires OpenAI network access",
  "models: downloads or loads large local models",
  "smoke: uses a user-provided recording",
]

[tool.coverage.run]
branch = true
source = ["scripts/audio_transcriber"]

[tool.coverage.report]
fail_under = 80
show_missing = true

[tool.ruff]
target-version = "py313"
line-length = 100

[tool.pyright]
pythonVersion = "3.13"
typeCheckingMode = "strict"
include = ["scripts/audio_transcriber", "tests"]
```

If Task 1 approved a different Python minor, update all three Python declarations together and amend the design before continuing. Run `uv lock --project plugins/transcribing-audio`; it must not create an environment. The subsequent sync creates only `plugins/transcribing-audio/.venv/`.

- [ ] **Step 5: Add the stdlib launcher and dependency Protocols**

`transcribe_audio.py` starts with `#!/usr/bin/env python3`, resolves `PLUGIN_ROOT`/`SCRIPTS_ROOT`, prepends only `SCRIPTS_ROOT` to `sys.path`, and calls `audio_transcriber.bootstrap.launch(sys.argv[1:])`. It contains no provider, model, dotenv, plugin SDK, or project imports. Mark it executable and extend `test_layout.py` with `os.access(launcher, os.X_OK)`.

`interfaces.py` initially defines only the stdlib `CommandRunner` Protocol. Every command accepts an argv sequence and optional environment; no interface accepts a shell command string. `test_layout.py` also imports `audio_transcriber` to prove the configured `pythonpath = ["scripts"]` works.

`constants.py` contains only immutable/machine-readable values: runtime/schema versions, stage names, CLI flag/default metadata, output suffixes and versioned quality-policy defaults. Modules and references import these values rather than repeating literals.

- [ ] **Step 6: Verify GREEN and commit**

Run:

```bash
export UV_PROJECT_ENVIRONMENT="$PWD/plugins/transcribing-audio/.venv"
uv sync --project plugins/transcribing-audio --frozen --all-extras --group dev
uv run --project plugins/transcribing-audio pytest plugins/transcribing-audio/tests/test_layout.py -q
```

Expected: PASS with exactly one `plugins/transcribing-audio/.venv`, ignored by Git. Also run the plugin validator once so Stage 1 cannot proceed with an invalid manifest:

```bash
python3 "$HOME/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py" plugins/transcribing-audio
```

Commit:

```bash
git add plugins/transcribing-audio .agents/plugins/marketplace.json docs/plans/2026-07-10-1820-transcribing-audio-plugin/checklist-transcribing-audio-plugin-stage-1-foundation.md
git commit -m "feat: scaffold isolated audio transcription plugin"
```

---

### Task 3: Define immutable cross-stage models and safe errors

**Files:**
- Create: `plugins/transcribing-audio/scripts/audio_transcriber/models.py`
- Create: `plugins/transcribing-audio/scripts/audio_transcriber/errors.py`
- Modify: `plugins/transcribing-audio/scripts/audio_transcriber/interfaces.py`
- Create: `plugins/transcribing-audio/tests/test_models.py`

**Interfaces:**
- Consumes: standard-library dataclasses, enums, pathlib and typing.
- Produces: `Mode`, `BackendFamily`, `ComputeDevice`, `RuntimeComponent`, `StageName`, `SpeakerCount`, `AudioStream`, `AudioMetadata`, `AudioWindow`, `AudioChunk`, `ASROptions`, `Word`, `AsrSegment`, `ASRChunkResult`, `DiarizationTurn`, `AlignedWord`, `TranscriptTurn`, `QualityIssue`, `QualityCheckResult`, `QualityReport`, `UploadConsent`, `OutputPaths`, `SafeError` and `redact_text`. Stage 3 extends this module with `TranscriptDocument` after its schema is defined.

- [ ] **Step 1: Write failing model tests**

Cover:

```python
def test_speaker_count_rejects_mixed_exact_and_range() -> None:
    with pytest.raises(ValueError, match="mutually exclusive"):
        SpeakerCount(exact=2, minimum=1, maximum=3)


def test_word_rejects_inverted_timestamp() -> None:
    with pytest.raises(ValueError, match="start"):
        Word(start_s=2.0, end_s=1.0, text="bad", confidence=None, source_chunk="chunk-0")


def test_safe_error_redacts_known_secrets() -> None:
    error = SafeError(stage=StageName.CONFIGURE, message="failed sk-live-secret")
    assert "sk-live-secret" not in error.render({"sk-live-secret"})
```

Also round-trip every persisted model through `to_dict` and `from_dict` and reject missing, extra, wrong-type, NaN, infinite, negative, or inverted timestamps.

- [ ] **Step 2: Run tests and verify RED**

Run `uv run --project plugins/transcribing-audio pytest plugins/transcribing-audio/tests/test_models.py -q`.

Expected: FAIL with missing `audio_transcriber.models`.

- [ ] **Step 3: Implement the shared contracts**

Use `@dataclass(frozen=True, slots=True)` and these exact enums:

```python
class Mode(StrEnum):
    LOCAL = "local"
    OPENAI = "openai"


class BackendFamily(StrEnum):
    MLX = "mlx"
    CUDA = "cuda"
    CPU = "cpu"


class ComputeDevice(StrEnum):
    MPS = "mps"
    CUDA = "cuda"
    CPU = "cpu"


class RuntimeComponent(StrEnum):
    ASR_MLX = "asr:mlx"
    ASR_CUDA = "asr:cuda"
    ASR_CPU = "asr:cpu"
    DIARIZATION_MPS = "diarization:mps"
    DIARIZATION_CUDA = "diarization:cuda"
    DIARIZATION_CPU = "diarization:cpu"


class StageName(StrEnum):
    CONFIGURE = "configure"
    INSPECT = "inspect"
    ASR = "asr"
    QUALITY = "quality"
    DIARIZE = "diarize"
    ALIGN = "align"
    RENDER = "render"
```

`SpeakerCount.as_pyannote_kwargs()` returns exact `min_speakers=max_speakers=N`, supplied range bounds, or an empty dict for automatic inference. `Word` requires timestamps and carries nullable `confidence` and chunk provenance. `ASROptions` contains model, language, word-timestamp requirement, independent-window flag, and deterministic recovery settings. `UploadConsent` contains provider, granted status, and interactive provenance; it is never serialized into run artifacts. Define every field listed by the source design's Output Contract; confidence alone is optional.

After defining these DTOs, extend `interfaces.py` with typed `ASRBackend.transcribe(chunk: AudioChunk, options: ASROptions) -> ASRChunkResult` and `DiarizationBackend.diarize(audio_path: Path, speakers: SpeakerCount) -> tuple[DiarizationTurn, ...]`. This ordering avoids `Any` or placeholder forward types in Task 2.

Use these exact cross-stage field contracts:

```python
@dataclass(frozen=True, slots=True)
class AudioStream:
    index: int
    codec_name: str
    channels: int
    sample_rate_hz: int


@dataclass(frozen=True, slots=True)
class AudioMetadata:
    duration_s: float
    format_name: str
    size_bytes: int
    streams: tuple[AudioStream, ...]


@dataclass(frozen=True, slots=True)
class AudioWindow:
    id: str
    start_s: float
    end_s: float
    overlap_before_s: float
    overlap_after_s: float


@dataclass(frozen=True, slots=True)
class AudioChunk:
    window: AudioWindow
    path: Path
    size_bytes: int
    sha256: str


@dataclass(frozen=True, slots=True)
class ASROptions:
    model: str
    language: str | None
    word_timestamps: bool = True
    condition_on_previous_text: bool = False
    temperature: float = 0.0
    beam_size: int | None = None


@dataclass(frozen=True, slots=True)
class Word:
    start_s: float
    end_s: float
    text: str
    confidence: float | None
    source_chunk: str


@dataclass(frozen=True, slots=True)
class AsrSegment:
    start_s: float
    end_s: float
    text: str
    words: tuple[Word, ...]
    average_log_probability: float | None
    no_speech_probability: float | None


@dataclass(frozen=True, slots=True)
class ASRChunkResult:
    chunk: AudioChunk
    backend: str
    model: str
    language: str | None
    segments: tuple[AsrSegment, ...]


@dataclass(frozen=True, slots=True)
class DiarizationTurn:
    start_s: float
    end_s: float
    raw_speaker: str


@dataclass(frozen=True, slots=True)
class AlignedWord:
    word: Word
    raw_speaker: str
    speaker: str


@dataclass(frozen=True, slots=True)
class TranscriptTurn:
    start_s: float
    end_s: float
    raw_speaker: str
    speaker: str
    text: str
    words: tuple[AlignedWord, ...]


@dataclass(frozen=True, slots=True)
class QualityIssue:
    code: str
    severity: Literal["warning", "error"]
    start_s: float
    end_s: float
    chunk_ids: tuple[str, ...]
    detail: str


@dataclass(frozen=True, slots=True)
class QualityCheckResult:
    code: str
    status: Literal["passed", "warning", "failed", "not_applicable"]
    detail: str


@dataclass(frozen=True, slots=True)
class QualityReport:
    policy_version: str
    status: Literal["passed", "failed"]
    checks: tuple[QualityCheckResult, ...]
    warnings: tuple[QualityIssue, ...]
    unresolved_errors: tuple[QualityIssue, ...]


@dataclass(frozen=True, slots=True)
class UploadConsent:
    provider: Literal["openai"]
    granted: bool
    interactive: bool


@dataclass(frozen=True, slots=True)
class OutputPaths:
    json: Path
    txt: Path
    srt: Path | None
    vtt: Path | None
```

- [ ] **Step 4: Implement safe error rendering**

`SafeError` exposes only stage, optional interval, backend, safe message, and recovery hint. `redact_text` replaces each non-empty exact secret and common `KEY=value` forms with `[REDACTED]`. It never serializes credential objects.

- [ ] **Step 5: Run model tests and commit**

Run:

```bash
uv run --project plugins/transcribing-audio pytest plugins/transcribing-audio/tests/test_models.py -q
uv run --project plugins/transcribing-audio pyright --project plugins/transcribing-audio/pyproject.toml
```

Expected: PASS.

Commit with `git commit -m "feat: define transcription runtime contracts"` after staging only the model/error files and tests.

---

### Task 4: Resolve configuration and credentials without leakage

**Files:**
- Create: `plugins/transcribing-audio/scripts/audio_transcriber/config.py`
- Create: `plugins/transcribing-audio/tests/test_config.py`

**Interfaces:**
- Consumes: `Mode`, `SpeakerCount` and parsed CLI values.
- Produces: `resolve_config(overrides: ConfigOverrides, repository_root: Path) -> ResolvedConfig`, `select_env_file(explicit: Path | None, repository_root: Path) -> Path | None` and non-serializable `Credentials`.

- [ ] **Step 1: Write precedence, validation and leakage tests**

Test CLI precedence, explicit-env-file exclusivity, repository discovery, secret allowlisting, ambient-environment non-interference, speaker-count invariants, secret-free repr, path control-character rejection, and the exact `--speaker-names "SPEAKER_00=Alice,SPEAKER_01=Bob"` mapping format.

- [ ] **Step 2: Run config tests and verify RED**

Run `uv run --project plugins/transcribing-audio pytest plugins/transcribing-audio/tests/test_config.py -q`.

Expected: FAIL with missing `audio_transcriber.config`.

- [ ] **Step 3: Implement exact precedence**

Use:

```text
safe defaults < selected repository dotenv < explicit dotenv < CLI
```

Repository discovery selects one file, not a merge: `.env` first, `.env.prod` only if `.env` is absent. An explicit `--env-file` bypasses discovery. Display the selected path but never values. Use `dotenv_values(path, interpolate=False)` without mutating `os.environ`; interpolation from ambient variables is disabled.

Ignore ambient `OPENAI_API_KEY`/`HF_TOKEN` because it is not a source in the approved precedence; pass selected credential values explicitly to provider/model constructors. `Credentials` uses private `repr=False` fields and has no `to_dict`. `ResolvedConfig` is frozen and its serialization omits credentials. Support exact, one-sided range, two-sided range, and automatic speaker counts.

Define `ConfigOverrides` with optional CLI-facing fields (`input_path` is required; mode/models/language/output/speaker counts/names/render/control flags may be unset) and define the resolved contract exactly:

```python
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
    credentials: Credentials
```

- [ ] **Step 4: Run tests, lint and commit**

Run:

```bash
uv run --project plugins/transcribing-audio pytest plugins/transcribing-audio/tests/test_config.py -q
uvx ruff check plugins/transcribing-audio/scripts/audio_transcriber/config.py plugins/transcribing-audio/tests/test_config.py
```

Expected: PASS. Commit with `git commit -m "feat: add secret-safe transcription configuration"`.

---

### Task 5: Probe MLX, CUDA and CPU deterministically

**Files:**
- Create: `plugins/transcribing-audio/scripts/audio_transcriber/bootstrap.py`
- Create: `plugins/transcribing-audio/tests/test_bootstrap.py`

**Interfaces:**
- Consumes: `CommandRunner` and injected `SystemInfo`.
- Produces: `probe_capabilities(runner: CommandRunner, system: SystemInfo) -> CapabilityReport` and `choose_backend(report: CapabilityReport) -> BackendFamily`.

- [ ] **Step 1: Write failing backend-selection tests**

Test MLX precedence on Apple Silicon with Metal, CUDA selection on healthy NVIDIA runtime, CPU fallback with recorded reason, Intel Mac exclusion, NVIDIA timeout, and separate pyannote compute-device choice.

- [ ] **Step 2: Run tests and verify RED**

Run `uv run --project plugins/transcribing-audio pytest plugins/transcribing-audio/tests/test_bootstrap.py -q`.

Expected: FAIL because `probe_capabilities` is absent.

- [ ] **Step 3: Implement the full probe**

- MLX requires Darwin, arm64, and bounded `system_profiler SPDisplaysDataType -json` Metal evidence.
- CUDA requires bounded `nvidia-smi --query-gpu=driver_version,compute_cap --format=csv,noheader` with a parseable row.
- CPU is the known-safe fallback.
- Subprocess calls use argv, `shell=False`, 10-second timeout, bounded/redacted output, and no secret environment values.
- `CapabilityReport` persists only safe OS, architecture, Python, backend, compute-device and fallback facts.

- [ ] **Step 4: Run focused tests and commit**

Expected: tests pass without real MLX/NVIDIA hardware. Commit with `git commit -m "feat: detect transcription runtime backend"`.

---

### Task 6: Cache, validate and provision the versioned runtime

**Files:**
- Modify: `plugins/transcribing-audio/scripts/audio_transcriber/bootstrap.py`
- Modify: `plugins/transcribing-audio/scripts/transcribe_audio.py`
- Modify: `plugins/transcribing-audio/tests/test_bootstrap.py`

**Interfaces:**
- Consumes: runtime version, lock SHA-256, OS/architecture, Python major/minor and `CapabilityReport`.
- Produces: `ensure_runtime(plugin_root: Path, reprobe: bool, runner: CommandRunner) -> RuntimeHandle`, `mark_runtime_component_unhealthy(runtime: RuntimeHandle, component: RuntimeComponent, reason: str) -> RecoveryTicket`, and `launch(argv: Sequence[str]) -> NoReturn`.

- [ ] **Step 1: Add failing fingerprint/cache/security tests**

Test missing `uv`/`ffmpeg`/`ffprobe`, unsafe input, unwritable private root, base/runtime fingerprint changes, cache hit without probe, invalidation/reprobe cases, `fcntl.flock` serialization, atomic writes, root mode `0700`, symlink rejection, and targeted rebuild that never touches model caches. Runtime fingerprint changes for either selected ASR backend or pyannote compute device.

- [ ] **Step 2: Implement the cheap runtime index**

Use:

```text
/tmp/psy-audio-transcriber-<uid>/runtime/index.json
/tmp/psy-audio-transcriber-<uid>/runtime/provision.lock
/tmp/psy-audio-transcriber-<uid>/runtime/unhealthy.json
/tmp/psy-audio-transcriber-<uid>/runtime/<fingerprint>/state.json
plugins/transcribing-audio/.venv/
```

The index stores schema, base fingerprint, backend and runtime fingerprint. The state stores safe probe facts and cached Python. A normal launch computes the cheap base fingerprint, validates both records and the executable, and does not probe.

Define `RuntimeHandle` as a frozen/slotted value with `runtime_fingerprint`, `base_fingerprint`, `python`, `backend`, `compute_device`, `state_path`, `plugin_root` and `recovery_attempt`. Derive `plugin_root` from the installed launcher's resolved path, never from repository cwd, and exclude that absolute installation path from persisted run/runtime fingerprints so moving or installing the same plugin does not invalidate otherwise compatible work. Define `CapabilityReport` with safe system facts, candidate backend/device availability, selected values and bounded fallback reasons; define `SystemInfo` as injected OS/architecture/Python facts so probes remain unit-testable.

Before probing or provisioning, a stdlib-only host preflight validates the input is a readable regular file, `uv`/`ffmpeg`/`ffprobe` are executable, and the private `/tmp` root can be created safely. It emits a prerequisite error without creating a venv when any check fails.

- [ ] **Step 3: Provision the single plugin-owned environment with uv**

Execute through argv and an explicit child environment:

```bash
UV_PROJECT_ENVIRONMENT="<plugin-root>/.venv" \
uv sync --project "<plugin-root>" --frozen --no-dev --all-extras --python "<approved-minor>"
```

Install all supported backend extras into the one reusable environment so backend fallback never provisions another environment. Validate its Python with `-c "import audio_transcriber"` and `PYTHONPATH=<plugin-root>/scripts` before publishing state.

Do not set `HF_HOME`, `HUGGINGFACE_HUB_CACHE`, `TRANSFORMERS_CACHE`, `TORCH_HOME`, or MLX model-cache variables in the uv/runtime child environment; model artifacts must remain in their normal persistent caches.

- [ ] **Step 4: Re-exec the CLI exactly once**

Set `PSY_AUDIO_RUNTIME_BOOTSTRAPPED=<runtime-fingerprint>` and `PYTHONPATH=<plugin-root>/scripts`, change cwd to the resolved plugin root, and `os.execve`:

```text
<cached-python> -P -m audio_transcriber.cli <original arguments>
```

Strip only bootstrap-owned `--reprobe`. If the marker already matches, bypass provisioning only when `Path(sys.executable).samefile(RuntimeHandle.python)` also holds; otherwise clear the marker and re-exec the cached interpreter. Test a forged marker, a root interpreter, a cwd shadow module, and a valid cached interpreter.

`mark_runtime_component_unhealthy` receives an exact `RuntimeComponent` value (`asr:mlx`, `asr:cuda`, `asr:cpu`, `diarization:mps`, `diarization:cuda`, or `diarization:cpu`). It atomically invalidates only the current runtime index and writes `unhealthy.json` with schema/base fingerprint, excluded component, bounded safe reason and timestamp. `probe_capabilities` accepts these durable backend/device exclusions and selects the next known-safe combination during internal one-shot recovery. Exclusions clear when the base fingerprint changes or when the user explicitly supplies `--reprobe`; the internal `PSY_AUDIO_RUNTIME_RECOVERY_ATTEMPT=1` path honors them so it cannot immediately reselect the failed component. Test all three cases and exit safely after one persistent startup failure.

- [ ] **Step 5: Verify cache behavior and commit**

Run bootstrap tests, strict pyright, and ruff. Expected: a fake second launch records zero probe calls. Commit with `git commit -m "feat: cache platform-specific transcription runtime"`.

---

## Stage 1 Completion Gate

Run:

```bash
export PLUGIN_ROOT="$PWD/plugins/transcribing-audio"
export UV_PROJECT_ENVIRONMENT="$PLUGIN_ROOT/.venv"
uv sync --project "$PLUGIN_ROOT" --frozen --all-extras --group dev
uv run --project "$PLUGIN_ROOT" pytest "$PLUGIN_ROOT/tests/test_layout.py" "$PLUGIN_ROOT/tests/test_models.py" "$PLUGIN_ROOT/tests/test_config.py" "$PLUGIN_ROOT/tests/test_bootstrap.py" -q
uv run --project "$PLUGIN_ROOT" pyright --project "$PLUGIN_ROOT/pyproject.toml"
uvx ruff check "$PLUGIN_ROOT"
uvx ruff format --check "$PLUGIN_ROOT"
git diff --check
```

Expected: all commands pass; exactly one Git-ignored plugin-local `.venv` exists; a cached launch test proves the probe is skipped; fixture secret values do not appear in captured logs, exceptions, manifests, or repr output.

Run `/simplify`, then walk and complete [the Stage 1 checklist](checklist-transcribing-audio-plugin-stage-1-foundation.md). Review the diff before Stage 2.
