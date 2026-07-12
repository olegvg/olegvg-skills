# Transcribing Audio Plugin Stage 4: CLI and Pipeline Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the validated runtime components into a safe interactive/non-interactive CLI with mandatory mode selection, explicit OpenAI consent, stage-level resume, targeted invalidation, and recoverable final publishing.

**Architecture:** `cli.py` owns parsing and user interaction only; `pipeline.py` owns the six-stage DAG and receives every external backend as an injected dependency. Each stage uses `RunStateStore` transactions. Final artifacts are copied into same-filesystem temporary paths, protected by an output lock/journal, validated as a set, and then published with rollback/recovery metadata.

**Tech Stack:** Python 3.13 argparse/typing/pathlib, Stage 1–3 runtime modules, pytest fakes, generated WAV plus optional real ffmpeg integration.

**Prerequisite:** Execute only after the [Stage 3 plan](plan-transcribing-audio-plugin-stage-3-diarization-output.md) is complete and the [Stage 3 checklist](checklist-transcribing-audio-plugin-stage-3-diarization-output.md) is approved.

## Global Constraints

- Complete and approve Stages 1–3 first.
- Every TTY run prompts for the input audio path, speaker-count policy, and `local` or `openai` even when matching CLI values supply defaults. These answers apply only to that run and are never retained as user defaults.
- Every non-TTY run requires an input path and `--mode`; it may pass exact/range speaker flags or omit them for automatic diarization.
- Interactive OpenAI mode always describes upload and asks confirmation.
- Non-interactive OpenAI mode requires `--allow-cloud-upload`; that flag cannot bypass an interactive prompt.
- Validate executable prerequisites, storage, credentials, provider capabilities, and speaker arguments before expensive ASR/diarization work where possible.
- Resume reuses only valid committed stages and rebuilds a corrupt stage plus descendants.
- Same-fingerprint concurrent runs serialize through the run lock.
- Successful outputs are never overwritten without `--overwrite`.
- Canonical JSON is the success anchor and must validate before final publishing begins.
- Interrupt returns 130, preserves completed stages, and emits no traceback unless `--debug` is explicitly set.

---

### Task 1: Build the argument and interaction contract

**Files:**
- Create: `plugins/transcribing-audio/scripts/audio_transcriber/cli.py`
- Create: `plugins/transcribing-audio/tests/test_cli.py`

**Interfaces:**
- Consumes: argv and injected text streams/prompt reader.
- Produces:

```python
def build_parser() -> argparse.ArgumentParser: ...
def resolve_interaction(
    args: argparse.Namespace,
    *,
    stdin: TextIO,
    stdout: TextIO,
) -> InteractionResult: ...
def main(
    argv: Sequence[str] | None = None,
    *,
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int: ...
```

- [ ] **Step 1: Write failing parser tests**

Define this exact public CLI:

```text
transcribe_audio.py INPUT
  [--mode {local,openai}]
  [--env-file PATH]
  [--language CODE]
  [--local-model ID]
  [--openai-model ID]
  [--speakers N | --min-speakers N] [--max-speakers N]
  [--speaker-names "SPEAKER_00=Alice,SPEAKER_01=Bob"]
  [--output-dir PATH]
  [--resume]
  [--overwrite]
  [--reprobe]
  [--srt]
  [--vtt]
  [--allow-cloud-upload]
  [--debug]
```

Exact count is mutually exclusive with either range flag. A one-sided min or max is allowed. `--speaker-names` is a comma-separated raw-label mapping, trims outer whitespace, rejects duplicate keys/names, and is resolved only after diarization. Defaults come from `ResolvedConfig`, not parser globals that could capture secrets.

- [ ] **Step 2: Write failing mode/consent matrix tests**

Cover:

| TTY | `--mode` | Selected mode | Consent behavior |
| --- | --- | --- | --- |
| yes | absent | prompt with no default | OpenAI selection prompts upload |
| yes | local/openai | prompt again with CLI value as default | OpenAI always prompts upload |
| no | absent | usage error | no provider call |
| no | local | local | upload flag rejected as irrelevant |
| no | openai, no flag | consent error | no provider call |
| no | openai + flag | openai | consent object created |

Interactive confirmation accepts only explicit case-insensitive `y`/`yes`. Empty, EOF, `n`, or other input denies. The message states that audio chunks leave the machine and names OpenAI, but never prints key/model-cache paths.

- [ ] **Step 3: Run tests and verify RED**

Run:

```bash
uv run --project plugins/transcribing-audio pytest plugins/transcribing-audio/tests/test_cli.py -q
```

Expected: FAIL with missing `audio_transcriber.cli`.

- [ ] **Step 4: Implement parser and interaction**

Use `stdin.isatty()` as the interaction boundary; redirected stdout must not turn human-readable TTY input into non-interactive mode. Write prompts to stderr or an injected prompt stream. Add tests for TTY stdin with redirected stdout and confirm `--allow-cloud-upload` still cannot bypass the prompt. Prompt for the current run's audio path and speaker policy before constructing `ResolvedConfig`: accept automatic inference, an exact positive count, or a positive min/max range; reject malformed or inverted bounds. Never persist prompt answers or silently reuse a prior file/count. Create immutable `UploadConsent(provider="openai", granted=True, interactive=<bool>)` only after positive confirmation/flag validation. Do not expose a public boolean that defaults true.

Define frozen/slotted `InteractionResult` with `mode`, `consent` and `interactive`; `main()` converts it into `ConfigOverrides` and never stores prompt text or secrets.

Return stable exit codes:

```text
0 success
2 CLI/configuration error
3 missing prerequisite or unwritable storage
4 upload consent denied/missing
5 provider/model/backend failure
6 unresolved ASR quality failure
130 keyboard interruption
```

`--debug` may include safe exception chaining but still passes messages through secret redaction.

- [ ] **Step 5: Verify GREEN and commit**

Run CLI tests and commit with `git commit -m "feat: add safe transcription CLI interaction"`.

---

### Task 2: Implement the six-stage pipeline and validators

**Files:**
- Create: `plugins/transcribing-audio/scripts/audio_transcriber/pipeline.py`
- Create: `plugins/transcribing-audio/tests/test_pipeline.py`
- Modify: `plugins/transcribing-audio/scripts/audio_transcriber/cli.py`

**Interfaces:**
- Consumes: `ResolvedConfig`, `RuntimeHandle`, `RunStateStore` and a frozen `PipelineDependencies` containing command runner, ASR backend factory, diarizer and clock.
- Produces:

```python
class PipelineRunner:
    def run(self, config: ResolvedConfig) -> OutputPaths: ...

def validate_inspect_stage(record: StageRecord) -> InspectArtifact: ...
def validate_asr_stage(record: StageRecord) -> AsrArtifact: ...
def validate_quality_stage(record: StageRecord) -> QualityArtifact: ...
def validate_diarization_stage(record: StageRecord) -> DiarizationArtifact: ...
def validate_alignment_stage(record: StageRecord) -> AlignmentArtifact: ...
def validate_render_stage(record: StageRecord) -> RenderArtifact: ...
```

Define the immutable stage DTOs exactly:

```python
class InspectArtifact:
    metadata: AudioMetadata
    normalized_audio: Path
    chunks: tuple[AudioChunk, ...]

class AsrArtifact:
    results: tuple[ASRChunkResult, ...]

class QualityArtifact:
    words: tuple[Word, ...]
    report: QualityReport
    retried_chunk_ids: tuple[str, ...]

class DiarizationArtifact:
    turns: tuple[DiarizationTurn, ...]

class AlignmentArtifact:
    words: tuple[AlignedWord, ...]
    turns: tuple[TranscriptTurn, ...]

class RenderArtifact:
    document: TranscriptDocument
    staged_paths: OutputPaths
```

Implement them as frozen/slotted dataclasses with explicit serialization validation. `PipelineDependencies` contains the `CommandRunner`, `ASRBackend` factory, `DiarizationBackend`, clock, and output publisher; no dependency is obtained from a global singleton.

- [ ] **Step 1: Write a failing happy-path pipeline test**

With generated WAV and fakes, assert exact call order and artifacts:

```text
stages/01-inspect/audio-metadata.json
stages/01-inspect/diarization.wav
stages/01-inspect/chunks.json
stages/01-inspect/chunks/<chunk-id>.flac
stages/02-asr/asr-raw.json
stages/03-quality/asr-validated.json
stages/03-quality/quality-report.json
stages/04-diarize/diarization.json
stages/05-align/aligned.json
stages/06-render/transcript.json
stages/06-render/transcript.txt
stages/06-render/transcript.srt       # only when requested
stages/06-render/transcript.vtt       # only when requested
```

The ASR stage uses mode-selected backend only; the diarization stage always invokes the local fake. `chunks.json` is committed only together with every `<chunk-id>.flac`; its validator checks each path is relative to the stage directory, regular, non-symlink, mode 0600, and matches the recorded `AudioChunk.sha256`.

- [ ] **Step 2: Write failing resume/invalidation tests**

For each stage, run once, then:

- `--resume` with valid artifacts causes zero calls for that stage;
- digest/schema/semantic corruption rebuilds that stage and every descendant only;
- changed run-fingerprint config selects a different run directory;
- interruption in a stage preserves earlier records and no current record;
- unresolved quality failure records evidence and calls neither diarizer nor renderer;
- two same-fingerprint runners serialize;
- non-resume run recomputes stages without deleting an existing successful final result.

- [ ] **Step 3: Run tests and verify RED**

Expected: missing `audio_transcriber.pipeline`.

- [ ] **Step 4: Implement orchestration without duplicated business logic**

For each stage:

1. On `resume`, ask `RunStateStore.get_valid_stage` with that stage's semantic validator.
2. If invalid, call `invalidate_stage_and_descendants`.
3. Execute only the module-level functions from Stages 2–3.
4. Write temporary artifacts within that stage directory.
5. Validate and `commit_stage` with safe provenance.
6. Pass only parsed immutable artifacts to the next stage.

Do not catch `KeyboardInterrupt` inside individual stages. The top pipeline boundary closes resources and lets `cli.main` return 130.

- [ ] **Step 5: Connect runtime-selected dependencies**

- `Mode.LOCAL + BackendFamily.MLX` → `MlxASR`.
- `Mode.LOCAL + CUDA/CPU` → `FasterWhisperASR`.
- `Mode.OPENAI` → `OpenAIASR` with consent; local backend remains irrelevant to ASR but `ComputeDevice` still selects pyannote device.
- All modes → `PyannoteDiarizer`.

Validate `HF_TOKEN` for all modes and `OPENAI_API_KEY` only for OpenAI before Stage 1 audio work. Validate ffmpeg/ffprobe and output directory writability at the same boundary.

If local ASR or pyannote startup raises the typed `BackendUnavailable` error before processing a chunk, map it to the exact `RuntimeComponent`, call Stage 1's `mark_runtime_component_unhealthy`, and re-enter bootstrap once. The next probe reads `unhealthy.json` and excludes that backend or device; the recovered runtime records the fallback reason. Never retry backend provisioning after audio/provider work has begun, and never loop after `PSY_AUDIO_RUNTIME_RECOVERY_ATTEMPT=1`.

After cheap tool/storage/config validation, run ffprobe inspection and reject malformed/non-audio input before model downloads. Then, before normalization, ASR, or any OpenAI upload, call `diarizer.health_check()` to load the gated local pipeline once and verify model access. In local mode also call `asr.health_check()` to initialize the selected model/device once. Reuse those loaded objects in their later stages. In OpenAI mode, validate the declared model capability locally but make no provider request during health check. The committed inspect stage still includes normalization/chunk materialization after these checks.

- [ ] **Step 6: Verify GREEN and commit**

Run pipeline/CLI tests. Commit with `git commit -m "feat: orchestrate resumable audio transcription"`.

---

### Task 3: Publish final outputs with lock, journal and recovery

**Files:**
- Modify: `plugins/transcribing-audio/scripts/audio_transcriber/pipeline.py`
- Modify: `plugins/transcribing-audio/scripts/audio_transcriber/renderers.py`
- Modify: `plugins/transcribing-audio/tests/test_pipeline.py`
- Modify: `plugins/transcribing-audio/tests/test_renderers.py`

**Interfaces:**
- Consumes: validated Stage 6 render artifacts and final `OutputPaths`.
- Produces:

```python
def publish_outputs(
    rendered: RenderArtifact,
    final: OutputPaths,
    *,
    overwrite: bool,
    run_store: RunStateStore,
) -> OutputPaths: ...

def recover_incomplete_publish(final: OutputPaths, run_store: RunStateStore) -> None: ...
```

- [ ] **Step 1: Write failing overwrite/rollback/recovery tests**

Test:

- existing target plus no `--overwrite` fails before changing any target;
- all source artifacts validate before target changes;
- same-filesystem temporary copies have matching digest;
- output lock serializes writers for the same stem;
- injected failure during the Nth replace restores previous successful files;
- simulated stale publish journal is recovered before a new run;
- successful journal records every target/digest and is marked complete only after all targets validate;
- canonical JSON and TXT are always published; SRT/VTT only when requested;
- no previous successful final is deleted by a partial run.

- [ ] **Step 2: Implement the output transaction**

Keep coordination state under the private runtime root:

```text
/tmp/psy-audio-transcriber-<uid>/output-locks/<target-set-digest>.lock
/tmp/psy-audio-transcriber-<uid>/publishes/<target-set-digest>.json
```

Only same-filesystem payloads/backups are transiently created beside final outputs:

```text
.<stem>.transcript.<run-fingerprint>.<format>.tmp
.<stem>.transcript.<run-fingerprint>.<format>.backup
```

Derive `target-set-digest` from canonical final paths, acquire its private lock, and validate the output directory as an owned non-symlink directory. For each temp/backup create a cryptographically random nonce name with `open(..., O_CREAT|O_EXCL|O_NOFOLLOW, 0o600)`, then verify ownership, regular-file type and mode before writing. Preflight targets with the same no-follow/ownership checks, copy Stage 6 files to same-filesystem temp files, fsync/validate/digest them, and atomically write a `/tmp` journal with target/temp/backup mappings. With overwrite, first `os.replace` each prior target to its backup. Replace new targets, fsync the output directory, validate all final digests, then mark the private journal complete and remove backups/temps. If `/tmp` has been cleared, fail closed and preserve existing final targets; do not guess at orphaned temp/backup ownership or delete files without the private journal. Unit tests precreate symlinks for every temp, backup and target path and assert no write follows them.

On a caught error, restore backups and remove newly published targets that had no predecessor. On next startup, an incomplete journal performs the same deterministic rollback before any new publish. Do not remove the run's validated Stage 6 artifacts.

- [ ] **Step 3: Verify GREEN and commit**

Run pipeline/renderer tests including injected failure at every transaction step. Commit with `git commit -m "feat: publish transcript outputs safely"`.

---

### Task 4: Add end-to-end integration coverage with deterministic backends

**Files:**
- Create: `plugins/transcribing-audio/tests/test_pipeline_integration.py`
- Modify: `plugins/transcribing-audio/tests/conftest.py`

**Interfaces:**
- Consumes: real generated WAV, real state/rendering, optional real ffmpeg, fake ASR and fake pyannote.
- Produces: subprocess-level evidence for CLI → pipeline → final artifacts.

- [ ] **Step 1: Write the integration fixture**

Generate a temporary WAV, deterministic overlapping ASR chunks with Russian/English words, and two raw speaker intervals. The fake ASR deliberately duplicates an overlap boundary but has no quality failure. Use temporary dotenv files with recognizable fake secrets and capture all stdout/stderr/logs.

- [ ] **Step 2: Test local non-interactive success**

Invoke `cli.main` or a subprocess equivalent with:

```text
INPUT --mode local --speakers 2 --speaker-names "SPEAKER_00=Alice,SPEAKER_01=Bob" --srt --vtt
```

Assert exit 0, canonical JSON word provenance, two raw labels, renamed display labels, exact TXT form, valid subtitles, and zero fake secret occurrences.

- [ ] **Step 3: Test OpenAI consent and quality stop**

First omit `--allow-cloud-upload` and assert exit 4 with zero fake provider calls. Then grant it and feed a repetition-loop response; assert exactly one retry and exit 6 when retry still fails, with no final output files.

- [ ] **Step 4: Test resume and targeted rebuild**

Run success twice with `--resume` and assert no stage backend calls on the second run. Corrupt `04-diarize/diarization.json`, run resume, and assert inspect/ASR/quality are reused while diarization/alignment/render/publish rerun.

- [ ] **Step 5: Run integration and commit**

Run:

```bash
uv run --project plugins/transcribing-audio pytest plugins/transcribing-audio/tests/test_pipeline_integration.py -q
```

Expected: PASS without network/model downloads. Commit with `git commit -m "test: cover transcription pipeline integration"`.

---

## Stage 4 Completion Gate

Run:

```bash
export PLUGIN_ROOT="$PWD/plugins/transcribing-audio"
uv run --project "$PLUGIN_ROOT" pytest \
  "$PLUGIN_ROOT/tests/test_cli.py" \
  "$PLUGIN_ROOT/tests/test_pipeline.py" \
  "$PLUGIN_ROOT/tests/test_pipeline_integration.py" -q
uv run --project "$PLUGIN_ROOT" pytest "$PLUGIN_ROOT/tests" -q
uv run --project "$PLUGIN_ROOT" pyright --project "$PLUGIN_ROOT/pyproject.toml"
uvx ruff check "$PLUGIN_ROOT"
uvx ruff format --check "$PLUGIN_ROOT"
git diff --check
```

Expected: complete default suite passes offline; mode/consent matrix is exhaustive; resume/corruption call counts prove targeted reuse; publish fault injection restores prior files; interruption returns 130 without losing completed state.

Run `/simplify`, then walk and complete [the Stage 4 checklist](checklist-transcribing-audio-plugin-stage-4-cli-integration.md). Review correctness/security before Stage 5.
