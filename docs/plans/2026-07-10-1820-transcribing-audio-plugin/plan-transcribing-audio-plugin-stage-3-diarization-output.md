# Transcribing Audio Plugin Stage 3: Diarization and Output Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add local pyannote diarization, deterministic word-to-speaker alignment, speaker renaming without identity enrollment, and validated canonical JSON/TXT/SRT/VTT rendering.

**Architecture:** Pyannote consumes the normalized local WAV and emits raw speaker intervals. A pure alignment layer assigns every ASR word by maximum overlap or deterministic nearest fallback, then merges adjacent same-speaker words. Renderers validate one immutable transcript document, write canonical JSON first, and derive every human-readable format solely from that document.

**Tech Stack:** Python 3.13, pyannote.audio, torch, standard-library JSON/path/time utilities, pytest with injected diarization pipeline.

**Prerequisite:** Execute only after the [Stage 2 plan](plan-transcribing-audio-plugin-stage-2-asr.md) is complete and the [Stage 2 checklist](checklist-transcribing-audio-plugin-stage-2-asr.md) is approved.

## Global Constraints

- Complete and approve Stages 1 and 2 first.
- Diarization always runs locally; no OpenAI or other cloud diarization.
- Support exact, one-sided/two-sided range, and automatic speaker counts.
- Exact mode passes `min_speakers=max_speakers=N` and validates N distinct raw labels.
- Preserve raw pyannote labels; no persistent voice profile, biometric enrollment, or cross-recording identification.
- Every ASR word receives a raw speaker label and retains timestamps/confidence/chunk provenance.
- Speaker names are a post-alignment display mapping and cannot collapse two raw labels.
- Canonical JSON is written and validated before any derived text/subtitle format.
- Word timestamps are mandatory; word confidence is nullable.
- Unresolved ASR quality errors make transcript validation fail.

---

### Task 1: Execute and validate local pyannote diarization

**Files:**
- Create: `plugins/transcribing-audio/scripts/audio_transcriber/diarization.py`
- Create: `plugins/transcribing-audio/tests/test_diarization.py`
- Create: `plugins/transcribing-audio/tests/fixtures/diarization/two-speakers.json`

**Interfaces:**
- Consumes: normalized mono 16 kHz WAV, `SpeakerCount`, `ComputeDevice`, `HF_TOKEN` and injected pipeline factory.
- Produces:

```python
class PyannoteDiarizer:
    def diarize(
        self,
        audio_path: Path,
        speakers: SpeakerCount,
    ) -> tuple[DiarizationTurn, ...]: ...

def validate_diarization(
    turns: Sequence[DiarizationTurn],
    *,
    duration_s: float,
    speakers: SpeakerCount,
) -> None: ...
```

- [ ] **Step 1: Write failing pipeline-argument tests**

Assert:

- exact 3 produces `{"min_speakers": 3, "max_speakers": 3}`;
- minimum-only, maximum-only and bounded range pass only supplied keys;
- automatic inference passes no speaker-count keys;
- model ID/revision are the approved Stage 1 values;
- pipeline moves to `mps`, `cuda` or `cpu` independently of ASR mode;
- token is passed through the Python API and never logged/serialized;
- model load is lazy and once per diarizer.

- [ ] **Step 2: Write failing output validation tests**

Cover sorted and overlapping turns, negative/inverted/out-of-duration intervals, empty labels, exact-count mismatch, automatic zero-speaker silence, arbitrary counts above two, and a provider exception containing a fake HF token.

Exact mode with silence or fewer/more distinct labels is a hard failure with requested/observed counts and recovery guidance; it never renames or merges labels to force the count.

- [ ] **Step 3: Run tests and verify RED**

Run:

```bash
uv run --project plugins/transcribing-audio pytest plugins/transcribing-audio/tests/test_diarization.py -q
```

Expected: FAIL with missing `audio_transcriber.diarization`.

- [ ] **Step 4: Implement the local adapter**

Use the current documented pyannote equivalent of:

```python
pipeline = Pipeline.from_pretrained(
    approved_model_id,
    token=credentials.hf_token,
    revision=approved_revision,
)
pipeline.to(torch.device(compute_device.value))
output = pipeline(str(audio_path), **speakers.as_pyannote_kwargs())
```

If the current factory does not accept `revision` directly, pin the model revision through the approved Hugging Face mechanism and capture it in the Stage 1 matrix; do not silently drop reproducibility. Convert `output.speaker_diarization` into immutable raw turns, sort by start/end/label, and validate before returning.

- [ ] **Step 5: Verify GREEN and commit**

Run tests with a fake pipeline; no model download. Commit:

```bash
git add plugins/transcribing-audio/scripts/audio_transcriber/diarization.py plugins/transcribing-audio/tests/test_diarization.py plugins/transcribing-audio/tests/fixtures/diarization/two-speakers.json
git commit -m "feat: add local speaker diarization"
```

---

### Task 2: Align every ASR word to a raw speaker deterministically

**Files:**
- Create: `plugins/transcribing-audio/scripts/audio_transcriber/alignment.py`
- Create: `plugins/transcribing-audio/tests/test_alignment.py`

**Interfaces:**
- Consumes: validated words, validated diarization turns and optional display-name mapping.
- Produces:

```python
def align_words(
    words: Sequence[Word],
    diarization: Sequence[DiarizationTurn],
) -> tuple[AlignedWord, ...]: ...

def rename_speakers(
    words: Sequence[AlignedWord],
    names: Mapping[str, str],
) -> tuple[AlignedWord, ...]: ...

def merge_turns(
    words: Sequence[AlignedWord],
    *,
    max_same_speaker_gap_s: float = 1.5,
) -> tuple[TranscriptTurn, ...]: ...
```

- [ ] **Step 1: Write failing maximum-overlap tests**

Test a word fully within one turn, straddling two turns with unequal overlap, equal-overlap tie, overlapping speakers, zero-duration punctuation word, unsorted input rejection, and no diarization data.

The tie order is exact:

1. greatest overlap duration;
2. earliest candidate turn start;
3. lexicographically smallest raw label.

- [ ] **Step 2: Write failing nearest-fallback tests**

For no overlap, interval distance is:

```python
distance = max(turn.start - word.end, word.start - turn.end, 0.0)
```

Choose smallest distance, then earliest turn start, then raw label. For a zero-duration word use its timestamp as a point. If diarization is empty while words exist, fail; do not invent `UNKNOWN`.

- [ ] **Step 3: Write failing rename/merge tests**

Assert:

- partial mapping leaves unspecified raw labels unchanged;
- unknown mapping keys fail;
- empty/control-character display names fail;
- duplicate display names for distinct raw labels fail to prevent label collapse;
- renaming never changes `raw_speaker`;
- adjacent same-speaker words merge only when gap is at most 1.5 seconds;
- speaker changes and larger gaps split turns;
- punctuation joins without an extra leading space while normal words use one space;
- every merged turn retains its immutable original aligned words.

- [ ] **Step 4: Run tests and verify RED**

Run `uv run --project plugins/transcribing-audio pytest plugins/transcribing-audio/tests/test_alignment.py -q`.

Expected: FAIL with missing `audio_transcriber.alignment`.

- [ ] **Step 5: Implement pure alignment and merging**

Use interval arithmetic only; no embeddings or learned speaker identity. Preserve ASR order and emit a new immutable object at each operation. Build text with a small deterministic punctuation set covering closing punctuation, opening punctuation, apostrophes and hyphens; tests include Latin and Cyrillic text.

- [ ] **Step 6: Verify GREEN and commit**

Run alignment tests and strict pyright. Commit with `git commit -m "feat: align transcript words to speakers"`.

---

### Task 3: Define and validate the canonical transcript document

**Files:**
- Modify: `plugins/transcribing-audio/scripts/audio_transcriber/models.py`
- Create: `plugins/transcribing-audio/scripts/audio_transcriber/renderers.py`
- Create: `plugins/transcribing-audio/tests/test_renderers.py`

**Interfaces:**
- Consumes: input identity, run/backend/model provenance, aligned words/turns, speaker configuration and passed quality report.
- Produces:

```python
def build_transcript_document(...) -> TranscriptDocument: ...
def validate_transcript(document: TranscriptDocument) -> None: ...
def render_json(document: TranscriptDocument, path: Path) -> Path: ...
def load_json(path: Path) -> TranscriptDocument: ...
```

- [ ] **Step 1: Write failing document validation tests**

The canonical document schema version `1` contains:

```text
schema_version
input {canonical_path, size, mtime_ns, sample_digest, duration_s}
language
asr {mode, backend, model, chunking, detected_language}
diarization {model, revision, compute_device, speaker_count_parameters}
provenance {runtime_version, run_fingerprint, completed_stages, retries}
speakers [{raw_label, display_name}]
turns [{start, end, raw_speaker, speaker, text, words[]}]
quality {policy_version, status, checks, warnings, unresolved_errors}
```

Test missing/extra fields, non-finite/out-of-bounds timestamps, unsorted/overlapping word order beyond tolerance, empty text, unknown speaker labels, exact-count mismatch, missing word provenance, unresolved quality errors, and JSON round-trip equality.

- [ ] **Step 2: Run tests and verify RED**

Expected: missing renderer/document behavior.

- [ ] **Step 3: Implement strict construction and validation**

Set `quality.status="passed"` only when unresolved errors are empty. Build `speakers` from every distinct label in the validated diarization artifact, even when a speaker has no aligned ASR word. Validate each turn bounds its words, turn text equals deterministic word joining, and every turn label is a subset of the diarization-derived speaker list. In exact mode validate N against that full speaker list. Reject a document with no words or no turns overall, but do not drop a correctly diarized silent/untranscribed speaker. Keep warnings but block errors.

`render_json` writes UTF-8, `ensure_ascii=False`, sorted stable keys and a trailing newline to the caller-provided stage temporary path. It parses the just-written file through `load_json` before returning; publishing remains Stage 4's responsibility.

- [ ] **Step 4: Verify GREEN and commit**

Run renderer/model tests. Commit with `git commit -m "feat: define canonical transcript output"`.

---

### Task 4: Derive readable TXT, SRT and VTT from canonical JSON

**Files:**
- Modify: `plugins/transcribing-audio/scripts/audio_transcriber/renderers.py`
- Modify: `plugins/transcribing-audio/tests/test_renderers.py`

**Interfaces:**
- Consumes: a `TranscriptDocument` returned by `load_json`.
- Produces:

```python
def render_txt(document: TranscriptDocument, path: Path) -> Path: ...
def render_srt(document: TranscriptDocument, path: Path) -> Path: ...
def render_vtt(document: TranscriptDocument, path: Path) -> Path: ...
def default_output_paths(input_path: Path, output_dir: Path, *, srt: bool, vtt: bool) -> OutputPaths: ...
```

- [ ] **Step 1: Write exact-format tests**

TXT line:

```text
[00:00:03–00:00:07] SPEAKER_00: Пример текста.
```

Floor TXT start to whole seconds and ceil end to whole seconds so a non-empty subsecond turn does not render zero duration. Use the Unicode en dash. SRT uses `HH:MM:SS,mmm` and sequential numeric cues; VTT starts with `WEBVTT` and uses `HH:MM:SS.mmm`. Speaker prefix and text come from the canonical turn.

Test recordings longer than 24 hours, Unicode, renamed speakers, empty paths, existing files at staging paths, and parseability of every produced format.

- [ ] **Step 2: Run tests and verify RED**

Expected: TXT/SRT/VTT functions missing.

- [ ] **Step 3: Implement derived renderers**

Every renderer accepts the in-memory document loaded from the canonical JSON artifact; it cannot accept backend-native results. Write to caller-provided temporary paths with `0600` and validate non-empty output plus format grammar before returning. Default final names are:

```text
<stem>.transcript.json
<stem>.transcript.txt
<stem>.transcript.srt
<stem>.transcript.vtt
```

- [ ] **Step 4: Verify GREEN and commit**

Run `test_renderers.py` and commit with `git commit -m "feat: render readable transcript formats"`.

---

## Stage 3 Completion Gate

Run:

```bash
export PLUGIN_ROOT="$PWD/plugins/transcribing-audio"
uv run --project "$PLUGIN_ROOT" pytest \
  "$PLUGIN_ROOT/tests/test_models.py" \
  "$PLUGIN_ROOT/tests/test_diarization.py" \
  "$PLUGIN_ROOT/tests/test_alignment.py" \
  "$PLUGIN_ROOT/tests/test_renderers.py" -q
uv run --project "$PLUGIN_ROOT" pyright --project "$PLUGIN_ROOT/pyproject.toml"
uvx ruff check "$PLUGIN_ROOT"
uvx ruff format --check "$PLUGIN_ROOT"
git diff --check
```

Expected: all tests pass without model downloads; exact/range/automatic pipeline arguments are proven; every word receives deterministic raw/display labels; JSON round-trips; TXT matches the specification; SRT/VTT parse.

Run `/simplify`, then walk and complete [the Stage 3 checklist](checklist-transcribing-audio-plugin-stage-3-diarization-output.md). Review the Stage 3 diff before Stage 4.
