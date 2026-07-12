# Audio Transcription and Diarization Skill Design

## Context

The repository needs a reusable standalone Codex plugin for frequent transcription of voice memos, meetings, and multi-speaker recordings. The existing `agent-cli` workflow is not suitable: its long-context MLX transcription produced repeated hallucinations, its Russian text-to-speaker alignment was too coarse, and its runtime management was opaque.

The new skill must run independently of `agent-cli`, use `uv` and an isolated virtual environment, support local and OpenAI transcription, perform local pyannote diarization for an arbitrary speaker count, expose real Python implementation modules, and use progressive disclosure.

## Goals

- Create a self-contained plugin under `plugins/transcribing-audio/`, exposed by the repository's Codex marketplace.
- Prompt for `local` or `OpenAI` mode on every interactive run.
- Read credentials from a selected `.env` file without exposing values.
- Detect MLX, CUDA, or CPU capability as early as possible and cache the result.
- Avoid a full platform probe on every run.
- Keep resumable runtime state under `/tmp` and exactly one isolated, Git-ignored virtual environment at the plugin root.
- Keep downloaded model artifacts in the platform's persistent cache.
- Resume multi-stage runs after interruption without recomputing successful stages.
- Support exact, ranged, or automatically inferred speaker counts.
- Produce word-timestamped, speaker-aligned JSON and readable text output.
- Detect and recover from repeated ASR hallucinations before publishing results.

## Non-goals

- Persistent speaker voice profiles or cross-recording biometric identification.
- Cloud diarization.
- Cloud providers other than OpenAI in the first version.
- A Docker runtime.
- A GUI.

## Considered Approaches

### Single PEP 723 script

A single `uv run --script` file would be compact, but backend-specific dependencies, cached probing, resumable stages, and unit testing would become difficult. Dependency resolution would also remain visible on more launches.

### Modular skill runtime with cached venv

This approach stores a small launcher, modular Python package, tests, references, `pyproject.toml`, and lock file inside the plugin. One Git-ignored `.venv` at the plugin root is reused for every backend; a versioned runtime state in `/tmp` records the selected MLX, CUDA, or CPU capability. This provides the required isolation, resumability, and testability without multiplying environments.

### Docker

Docker gives strong isolation but complicates Metal/CUDA access, filesystem permissions, model caches, and daily use with local recorder files.

## Decision

Use the modular skill runtime with one cached plugin-local venv and platform-specific cached runtime state.

## Skill Layout

```text
plugins/transcribing-audio/
├── SKILL.md
├── pyproject.toml
├── uv.lock
├── agents/
│   └── openai.yaml
├── scripts/
│   ├── transcribe_audio.py
│   └── audio_transcriber/
│       ├── __init__.py
│       ├── bootstrap.py
│       ├── cli.py
│       ├── config.py
│       ├── state.py
│       ├── audio.py
│       ├── asr_local.py
│       ├── asr_openai.py
│       ├── diarization.py
│       ├── alignment.py
│       ├── quality.py
│       └── renderers.py
├── references/
│   ├── runtime-and-backends.md
│   ├── local-asr.md
│   ├── openai-asr.md
│   ├── diarization-and-alignment.md
│   ├── quality-and-recovery.md
│   └── output-schema.md
└── tests/
```

The implementation may consolidate modules when tests show that a boundary adds no value, but no module should combine unrelated responsibilities.

## Progressive Disclosure

`SKILL.md` contains only:

- triggering situations and privacy constraints;
- a short mode-selection workflow;
- the stage sequence and stop conditions;
- common commands;
- a routing table that states when each reference must be read.

Detailed backend behavior, provider specifics, recovery procedures, and schemas live in one-level reference files. Executable behavior lives in scripts and can run without loading source code into the model context. References do not duplicate `SKILL.md` content.

## Runtime Bootstrap

The launcher computes a runtime fingerprint from:

- skill runtime version;
- lock-file digest;
- operating system and architecture;
- selected backend family;
- Python major/minor version.

State lives under `/tmp/transcribing-audio-<uid>/runtime/<fingerprint>/`. The only environment lives at `plugins/transcribing-audio/.venv/`; a normal launch validates the state schema and that environment's Python executable. A full probe runs when state is absent, invalid, version-mismatched, or explicitly bypassed with `--reprobe`.

The full probe selects backends in this order:

1. MLX on Apple Silicon when a Metal device is available.
2. faster-whisper CUDA when NVIDIA runtime checks pass.
3. faster-whisper CPU.

The bootstrap uses `uv` to create or update the one Git-ignored plugin-local venv with all locked backend dependencies, then writes state atomically. A backend change never provisions another environment. Model caches remain persistent through their normal platform locations, such as Hugging Face cache directories; they are not stored under `/tmp`.

## Configuration and Secrets

Configuration precedence is:

1. CLI arguments.
2. Explicit `--env-file` values.
3. Repository `.env` and then `.env.prod` discovery.
4. Safe defaults.

The CLI asks for `local` or `OpenAI` mode on every interactive run. Non-interactive runs require `--mode`. Before an OpenAI run, the CLI states that audio chunks will leave the machine and requires explicit confirmation unless an explicit non-interactive consent flag is present.

Only `OPENAI_API_KEY` and Hugging Face credentials required by pyannote are loaded. Secret values must never appear in logs, manifests, subprocess command strings, exceptions, or output artifacts.

## Run Identity and State

A run fingerprint includes the canonical input path, size, modification time, content sample digest, relevant configuration, and runtime version. Stage state lives under `/tmp/transcribing-audio-<uid>/runs/<run-fingerprint>/`.

Each stage:

1. Reads only validated outputs from preceding stages.
2. Writes to a temporary path.
3. Validates its artifact and metadata.
4. Atomically renames the artifact and marks the stage complete.

`--resume` reuses valid stages. A changed input or configuration creates a different run. A partial run never overwrites a previous successful final result.

## Pipeline

### Stage 0: Bootstrap and configuration

Resolve repository and skill paths, load configuration, select or provision the runtime, and prompt for local or OpenAI mode.

### Stage 1: Inspect and normalize

Use ffprobe to capture duration, streams, channels, sample rate, and container metadata. Convert a temporary diarization copy to mono 16 kHz PCM while preserving the original input.

### Stage 2: Timestamped ASR

Local mode uses MLX Whisper or faster-whisper. Decode independent windows with `condition_on_previous_text=false`, word timestamps, bounded overlap, and deterministic merging. This is mandatory because long inherited context caused a verified repetition loop in the source workflow.

OpenAI mode chunks input below current provider limits, requests timestamp-capable transcription, preserves chunk provenance, offsets timestamps, and deduplicates overlap boundaries. Provider behavior must be based on current official OpenAI documentation at implementation time.

### Stage 3: ASR quality gates and recovery

Validate:

- monotonic timestamps within source duration;
- expected coverage;
- empty or implausibly long segments;
- repeated n-grams and low-entropy phrase loops;
- excessive compression ratios or low-confidence words where available;
- overlap deduplication.

Retry only failing chunks with stricter isolated decoding. If the retry still fails, record the exact interval and stop before generating a successful final artifact.

### Stage 4: Local diarization

Run pyannote locally. Speaker options are mutually exclusive:

- `--speakers N` sets exact `min_speakers=max_speakers=N`;
- `--min-speakers` and `--max-speakers` provide a range;
- omission enables automatic inference.

Validate that exact-count mode returns the requested number of raw labels. Do not silently collapse labels through persistent speaker profiles.

### Stage 5: Word-to-speaker alignment

Assign each ASR word to the pyannote speaker with the greatest temporal overlap. Use a deterministic nearest-speaker fallback only for uncovered words. Merge adjacent words into readable turns without losing original word-level provenance.

Optional `--speaker-names` renames labels after alignment. It does not enroll or identify voices across recordings.

### Stage 6: Render and validate

Write canonical JSON first. Derive TXT and optional SRT/VTT from canonical JSON. Validate speaker count, chronological ordering, duration bounds, non-empty text, artifact parseability, and absence of unresolved ASR quality failures before atomically publishing outputs.

## Output Contract

The canonical JSON includes:

- input identity and duration;
- language;
- selected ASR mode, backend, and model;
- diarization model and speaker-count parameters;
- stage and retry provenance;
- speaker list;
- timestamped turns;
- optional word-level timestamps and confidence;
- quality-gate results and warnings.

The readable TXT format is:

```text
[HH:MM:SS–HH:MM:SS] SPEAKER_00: Text
```

Default output names are `<stem>.transcript.json` and `<stem>.transcript.txt`. Existing successful outputs require an explicit overwrite flag.

## Error Handling

- Missing ffmpeg, uv, credentials, model access, or writable storage fails before expensive work where possible.
- Platform probe failures fall back only to a known-safe slower backend and record the reason.
- Cloud upload is never implicit.
- Keyboard interruption preserves completed stage artifacts.
- State corruption triggers a targeted rebuild rather than deletion of unrelated caches.
- Exceptions include stage, interval, backend, and recovery guidance while redacting secrets.

## Testing Strategy

Follow TDD for the runtime and TDD-style baseline/forward testing for the skill.

Unit tests cover runtime fingerprints, state validity, platform selection, audio chunking, overlap deduplication, repetition detection, timestamp validation, word-to-speaker alignment, and renderers. Integration tests use a generated temporary WAV and deterministic ASR/diarization fixtures. Network and large-model tests are opt-in.

An opt-in smoke test may use a user-provided recording without committing it. It must verify that a known long-context repetition is detected or avoided and that exact speaker-count mode preserves every requested label.

Target at least 80% coverage for executable runtime code.

Skill validation follows RED-GREEN-REFACTOR:

1. Run a realistic transcription request without the new skill and record omissions or unsafe shortcuts.
2. Implement the minimal skill and scripts that address observed failures.
3. Run the same scenario with the skill and inspect commands and artifacts.
4. Refine instructions only for observed gaps.

## Acceptance Criteria

- The skill is discoverable from natural requests for transcription, diarization, voice memos, meetings, or speaker-labelled audio.
- First launch provisions an isolated runtime; subsequent launches avoid a full probe.
- MLX, CUDA, and CPU backend selection is deterministic and recoverable.
- Every interactive run asks local versus OpenAI.
- OpenAI mode loads `OPENAI_API_KEY` from `.env` and requires upload confirmation.
- Exact, ranged, and automatic speaker counts work.
- ASR output contains usable timestamps and is aligned by word to raw pyannote labels.
- Repetition loops fail quality gates and trigger isolated retry rather than entering final output.
- Interrupted runs resume by stage.
- Final JSON and TXT pass structural validation.
- Runtime tests reach at least 80% coverage.
- The skill passes quick validation and a forward-test scenario.
