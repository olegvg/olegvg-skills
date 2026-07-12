# Transcribing Audio Plugin Stage 2: Resumable ASR Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement resumable run state, validated media preparation, timestamped local/OpenAI transcription, deterministic overlap merging, ASR quality gates, and one bounded recovery pass.

**Architecture:** A run fingerprint selects an isolated state directory guarded by a per-run lock. Audio is inspected and normalized once, both ASR modes emit the same immutable word contract, and a backend-neutral quality layer blocks downstream processing until every interval passes or one stricter retry succeeds.

**Tech Stack:** Python 3.13, ffprobe/ffmpeg, hashlib/json/zlib, MLX Whisper, faster-whisper, OpenAI Audio Transcriptions API, pytest with injected command/provider adapters.

**Prerequisite:** Execute only after the [Stage 1 plan](plan-transcribing-audio-plugin-stage-1-foundation.md) is complete and the [Stage 1 checklist](checklist-transcribing-audio-plugin-stage-1-foundation.md) is approved.

## Global Constraints

- Complete and approve Stage 1 first.
- Preserve the original input; every temporary artifact stays under the run state directory.
- Run identity includes canonical path, size, modification time, sampled content, relevant configuration, and runtime version.
- Never pass file paths or secrets through `shell=True`.
- Local ASR always uses independent windows, word timestamps, and `condition_on_previous_text=false`.
- OpenAI uploads only preplanned chunks below the verified provider ceiling and always returns word timestamps.
- OpenAI consent is an explicit constructor requirement; the CLI creates it in Stage 4.
- Network/model tests remain opt-in; default tests use deterministic fixtures.
- Quality failures are persisted as failure evidence but never become successful final output.
- Resume trusts only schema-valid artifacts whose recorded SHA-256 matches.

---

### Task 1: Implement run identity and atomic stage state

**Files:**
- Create: `plugins/transcribing-audio/scripts/audio_transcriber/state.py`
- Create: `plugins/transcribing-audio/tests/test_state.py`

**Interfaces:**
- Consumes: `ResolvedConfig`, runtime version and input `Path`.
- Produces:

```python
def compute_input_identity(path: Path) -> InputIdentity: ...
def compute_run_fingerprint(
    identity: InputIdentity,
    config: ResolvedConfig,
    runtime_fingerprint: str,
) -> str: ...

FileValidator = Callable[[Path], None]
StageValidator = Callable[[StageRecord], T]


@dataclass(frozen=True, slots=True)
class PendingArtifact:
    temp_path: Path
    final_relative_path: Path
    validator: FileValidator

class RunStateStore:
    def acquire(self) -> AbstractContextManager[None]: ...
    def get_valid_stage(self, stage: StageName, validator: StageValidator[T]) -> T | None: ...
    def commit_stage(self, stage: StageName, pending: Sequence[PendingArtifact], provenance: Mapping[str, JsonValue]) -> StageRecord: ...
    def record_failure(self, stage: StageName, report: Mapping[str, JsonValue]) -> Path: ...
    def invalidate_stage_and_descendants(self, stage: StageName) -> None: ...
```

Define the persisted state types exactly: `InputIdentity` has canonical path, size, mtime_ns and sample digest; `StageRecord` has schema version, stage, run fingerprint, final relative artifact paths, artifact SHA-256 mapping, safe provenance and completion timestamp; `FileValidator` is `Callable[[Path], None]`; `StageValidator[T]` is `Callable[[StageRecord], T]`; and `JsonValue` is a recursive JSON-safe type alias. `RunStateStore` is constructed with one private run root and never accepts an output-directory path.

- [ ] **Step 1: Write failing fingerprint tests**

Assert:

- relative/symlink spellings resolve to one canonical identity;
- size, `mtime_ns`, any sampled block, ASR mode/model/language, diarization model/revision, speaker-count configuration, full runtime fingerprint, window size, or overlap changes the fingerprint;
- output directory, `--resume`, and `--overwrite` do not change it;
- `--srt`, `--vtt`, or speaker display-name mapping changes the fingerprint so resume cannot reuse an incompatible render stage;
- the sample digest reads the entire file below 5 MiB and five 1 MiB blocks (start, 25%, 50%, 75%, tail) for larger files;
- unreadable, non-regular, or changing-during-hash input fails before state creation.

- [ ] **Step 2: Write failing stage-state tests**

Test schema mismatch, malformed JSON, missing artifacts, digest mismatch, validator failure, atomic commit, descendant invalidation, concurrent per-run locking, interruption before rename, and `0700` root permissions. A `KeyboardInterrupt` must leave earlier stage records valid and the current stage absent.

- [ ] **Step 3: Run tests and verify RED**

Run:

```bash
uv run --project plugins/transcribing-audio pytest plugins/transcribing-audio/tests/test_state.py -q
```

Expected: FAIL with missing `audio_transcriber.state`.

- [ ] **Step 4: Implement identity and run layout**

Use canonical JSON with sorted keys and compact separators before SHA-256. Include `RuntimeHandle.runtime_fingerprint` so lock/backend/compute-device changes cannot reuse old run artifacts. Exclude credentials and control-only flags. After normalization/chunk materialization, re-stat and recompute the source identity before committing Stage 1; if size, mtime, or sampled content differs, discard the private normalized/chunk artifacts and fail with a changed-input error. Use:

```text
/tmp/psy-audio-transcriber-<uid>/runs/<run-fingerprint>/
├── run.lock
├── manifest.json
├── failures/
└── stages/
    ├── 01-inspect/
    ├── 02-asr/
    ├── 03-quality/
    ├── 04-diarize/
    ├── 05-align/
    └── 06-render/
```

Reject a root or run path that is a symlink or not owned by the current UID. Create private directories with mode `0700` and regular artifacts with `0600`.

- [ ] **Step 5: Implement atomic stage transactions**

Write each artifact to a unique sibling `.tmp-<pid>-<uuid>` path, flush and fsync it, then pass `PendingArtifact(temp_path, final_relative_path, validator)` to `commit_stage`. The transaction validates each temp and snapshots any existing final path to a private random backup before replacing it. It computes SHA-256 from every final file and atomically replaces `manifest.json` with schema version, artifact-relative paths, hashes, provenance, and completion timestamp. On any failure, restore all backups in reverse order, remove only newly created finals, and leave the previous manifest and files valid. On success, remove backups after the new manifest is durable. Never store absolute external paths or secrets in provenance.

`record_failure` writes a safe report under `failures/` without marking the stage complete. `invalidate_stage_and_descendants` removes only manifest records and same-run derived artifacts; it cannot traverse outside the run root.

- [ ] **Step 6: Verify GREEN and commit**

Run test_state, pyright and ruff. Expected: PASS. Commit:

```bash
git add plugins/transcribing-audio/scripts/audio_transcriber/state.py plugins/transcribing-audio/tests/test_state.py
git commit -m "feat: add resumable transcription stage state"
```

---

### Task 2: Inspect, normalize and plan independent audio chunks

**Files:**
- Create: `plugins/transcribing-audio/scripts/audio_transcriber/audio.py`
- Create: `plugins/transcribing-audio/tests/test_audio.py`
- Modify: `plugins/transcribing-audio/tests/conftest.py`

**Interfaces:**
- Consumes: `CommandRunner`, source path and `AudioMetadata`.
- Produces:

```python
def require_audio_tools(which: Callable[[str], str | None]) -> AudioTools: ...
def inspect_audio(path: Path, runner: CommandRunner, tools: AudioTools) -> AudioMetadata: ...
def normalize_for_diarization(source: Path, destination: Path, runner: CommandRunner, tools: AudioTools) -> Path: ...
def plan_chunks(metadata: AudioMetadata, *, max_duration_s: float, overlap_s: float) -> tuple[AudioWindow, ...]: ...
def materialize_chunk(source: Path, window: AudioWindow, destination: Path, runner: CommandRunner, tools: AudioTools) -> AudioChunk: ...
def measure_mean_volume_dbfs(chunk: AudioChunk, runner: CommandRunner, tools: AudioTools) -> float: ...
```

- [ ] **Step 1: Add a generated WAV fixture and failing tests**

`conftest.py` generates a small mono/stereo WAV with `wave`; do not commit binary audio. Tests cover:

- missing `ffmpeg` or `ffprobe` fails before any model/provider call;
- ffprobe JSON parsing rejects no-audio, zero/NaN duration, invalid sample rate and malformed JSON;
- paths with spaces and Unicode remain one argv element;
- normalized output is mono 16 kHz PCM and original bytes are unchanged;
- chunks cover `[0, duration]`, have bounded overlap, positive duration and stable IDs;
- mean-volume parsing classifies generated silence and tone fixtures deterministically;
- `overlap_s >= max_duration_s` is rejected;
- materialization writes to the requested temporary path and validates resulting duration.

- [ ] **Step 2: Run tests and verify RED**

Run `uv run --project plugins/transcribing-audio pytest plugins/transcribing-audio/tests/test_audio.py -q`.

Expected: FAIL with missing `audio_transcriber.audio`.

- [ ] **Step 3: Implement inspection and normalization commands**

Use argv equivalent to:

```bash
ffprobe -v error -show_entries \
  format=duration,format_name,size:stream=index,codec_type,codec_name,sample_rate,channels \
  -of json "<input>"

ffmpeg -nostdin -hide_banner -loglevel error -i "<input>" \
  -map 0:a:0 -vn -ac 1 -ar 16000 -c:a pcm_s16le "<temporary-normalized.wav>"
```

The displayed quoting is documentation only; implementation passes an argv list. Validate ffmpeg output with a second ffprobe before stage commit.

- [ ] **Step 4: Implement deterministic chunk planning**

`AudioWindow` contains `id`, `start_s`, `end_s`, `overlap_before_s`, and `overlap_after_s` but no filesystem path. For window index `i`:

```python
start = 0.0 if i == 0 else previous_end - overlap_s
end = min(start + max_duration_s, source_duration_s)
```

Stop when `end >= duration`; round persisted timestamps to microseconds, never cumulative integer milliseconds. `materialize_chunk` writes FLAC with `-ss` before `-i`, `-t`, mono 16 kHz, and `-c:a flac`, then returns a new immutable `AudioChunk(window, path, size_bytes, sha256)`. If an OpenAI chunk exceeds the provider byte ceiling, bisect its window and materialize new child chunks until every child is under the ceiling; reject intervals below one second rather than upload an oversized file.

`measure_mean_volume_dbfs` runs bounded ffmpeg `volumedetect` on the materialized chunk, parses only `mean_volume`, and returns negative infinity for digital silence. It does not infer that a missing ASR result is silence; the quality layer uses it only after confirming a result exists and is explicitly empty.

- [ ] **Step 5: Verify GREEN and commit**

Run audio tests plus an integration invocation when ffmpeg is present. Mark only the external-tool test skipped when unavailable; pure unit tests must pass. Commit with `git commit -m "feat: inspect and chunk transcription audio"`.

---

### Task 3: Merge backend-neutral timestamped ASR results

**Files:**
- Create: `plugins/transcribing-audio/scripts/audio_transcriber/asr.py`
- Create: `plugins/transcribing-audio/tests/test_asr.py`
- Create: `plugins/transcribing-audio/tests/fixtures/asr/overlap-boundary.json`

**Interfaces:**
- Consumes: ordered `ASRChunkResult` values with chunk-relative words.
- Produces:

```python
def offset_words(result: ASRChunkResult) -> tuple[Word, ...]: ...
def deduplicate_overlap(left: Sequence[Word], right: Sequence[Word], overlap: Interval) -> tuple[Word, ...]: ...
def merge_chunk_results(results: Sequence[ASRChunkResult]) -> tuple[Word, ...]: ...
```

- [ ] **Step 1: Write failing merge tests**

Cover exact duplicate boundary phrases, punctuation/case variants, no-match overlap, timestamp-identical duplicates, three chunks, empty/silent chunks, non-monotonic backend results, and provenance preservation.

- [ ] **Step 2: Run tests and verify RED**

Expected: missing `audio_transcriber.asr`.

- [ ] **Step 3: Implement offset and deduplication**

Normalize matching tokens with Unicode case-folding and surrounding punctuation removal, without changing emitted text. Inside the declared overlap, find the longest suffix/prefix match of 1–20 normalized words whose paired midpoint differences are at most 0.75 seconds. Remove only the matched prefix from the right chunk. If there is no sequence match, remove a right word only when normalized text matches and interval IoU is at least 0.5. Sort by start/end/chunk index and reject remaining backwards timestamps instead of silently reordering invalid backend output.

- [ ] **Step 4: Verify GREEN and commit**

Run `test_asr.py`, type check, and commit with `git commit -m "feat: merge timestamped ASR chunks"`.

---

### Task 4: Implement MLX and faster-whisper adapters

**Files:**
- Create: `plugins/transcribing-audio/scripts/audio_transcriber/asr_local.py`
- Create: `plugins/transcribing-audio/tests/test_asr_local.py`

**Interfaces:**
- Consumes: `AudioChunk`, `ASROptions`, selected `BackendFamily`, and injected MLX/faster factories.
- Produces: `MlxASR.transcribe(chunk, options) -> ASRChunkResult` and `FasterWhisperASR.transcribe(chunk, options) -> ASRChunkResult`.

- [ ] **Step 1: Write failing adapter tests**

Assert both adapters request word timestamps and `condition_on_previous_text=False`; model loading is lazy and once per adapter; CUDA uses the Stage 1-approved compute type; CPU uses int8; language is forwarded; backend word/segment values are strictly parsed; and backend exceptions become redacted `SafeError` values with chunk interval/backend.

- [ ] **Step 2: Run tests and verify RED**

Expected: missing `audio_transcriber.asr_local`.

- [ ] **Step 3: Implement MLX translation**

Call the current documented equivalent of:

```python
mlx_whisper.transcribe(
    str(chunk.path),
    path_or_hf_repo=options.model,
    language=options.language,
    word_timestamps=True,
    condition_on_previous_text=False,
)
```

Require non-empty words for non-silent backend segments and keep chunk-relative timestamps. Do not use `clip_timestamps` because chunks are materialized independently.

- [ ] **Step 4: Implement faster-whisper translation**

Initialize `WhisperModel` with `device="cuda", compute_type=<approved>` or `device="cpu", compute_type="int8"`. Invoke current documented `transcribe` with `word_timestamps=True` and `condition_on_previous_text=False`. Exhaust its lazy segment generator inside the adapter so provider exceptions occur within safe error handling.

When `--language` is absent, the first non-empty chunk establishes detected language; persist it and pass it to later chunks and retries. Reject a material language change rather than merging multilingual detections silently.

- [ ] **Step 5: Verify GREEN and commit**

Run local adapter tests without importing unavailable hardware packages by injecting factories. Commit with `git commit -m "feat: add local timestamped ASR backends"`.

---

### Task 5: Implement capability-checked OpenAI transcription

**Files:**
- Create: `plugins/transcribing-audio/scripts/audio_transcriber/asr_openai.py`
- Create: `plugins/transcribing-audio/tests/test_asr_openai.py`

**Interfaces:**
- Consumes: injected `TranscriptionsClient`, immutable `UploadConsent`, `AudioChunk`, `ASROptions` and the Stage 1 provider capability decision.
- Produces: `OpenAIASR.transcribe(chunk, options) -> ASRChunkResult`.

- [ ] **Step 1: Recheck the official API contract**

Use `openai-docs` immediately before implementation. Confirm the selected model accepts the Audio Transcriptions endpoint and returns word timestamps. Update the capability entry and fixture response together if official fields changed. Never silently use a model/format without word timestamps; reject it before opening the audio file.

- [ ] **Step 2: Write failing consent, request and response tests**

Test:

- absent consent prevents client invocation;
- absent API key fails before file read;
- file size at/over ceiling is rejected;
- request contains selected model, language when present, timestamp-capable response format/granularity, and temperature 0;
- response word offsets remain chunk-relative until `asr.py` merges them;
- malformed/missing words fail;
- status/rate-limit/provider exceptions are redacted and contain safe retry guidance;
- the fake API key is absent from captured request repr, logs and errors.

- [ ] **Step 3: Implement the provider adapter**

For the currently documented verbose word-timestamp contract, call the SDK equivalent of:

```python
client.audio.transcriptions.create(
    model=options.model,
    file=audio_file,
    language=options.language,
    response_format="verbose_json",
    timestamp_granularities=["word", "segment"],
    temperature=0,
)
```

If current official docs require a different supported model/shape, use that exact shape and capture it in tests/reference; the invariant is mandatory word timestamps, not the remembered parameter names. Open files only inside a context manager. Do not log SDK request objects.

- [ ] **Step 4: Verify GREEN and commit**

Run `test_asr_openai.py` with an injected fake client; do not make network calls. Commit with `git commit -m "feat: add consent-gated OpenAI transcription"`.

---

### Task 6: Gate ASR quality and retry only failing intervals

**Files:**
- Create: `plugins/transcribing-audio/scripts/audio_transcriber/quality.py`
- Create: `plugins/transcribing-audio/tests/test_quality.py`
- Create: `plugins/transcribing-audio/tests/fixtures/asr/repetition-loop-ru.json`

**Interfaces:**
- Consumes: chunk results, source duration, `QualityPolicy` and injected retry callback.
- Produces:

```python
def evaluate_asr(
    planned_chunks: Sequence[AudioChunk],
    results: Sequence[ASRChunkResult],
    *,
    source_duration_s: float,
    policy: QualityPolicy,
    mean_volume_dbfs: Callable[[AudioChunk], float],
) -> QualityReport: ...
def recover_failed_chunks(
    results: Sequence[ASRChunkResult],
    report: QualityReport,
    retry: Callable[[AudioChunk, RecoveryOptions], ASRChunkResult],
    policy: QualityPolicy,
) -> RecoveryResult: ...
```

Define immutable `RecoveryOptions` (window duration, overlap, language, temperature, beam size) and `RecoveryResult` (replacement results, retried IDs, final report, unresolved intervals). The retry callback accepts a newly materialized `AudioChunk` and these options; it never mutates the original result.

- [ ] **Step 1: Define versioned thresholds and failing fixtures**

Use an immutable `QualityPolicy(version="1")` with:

```python
timestamp_epsilon_s = 0.05
silence_mean_volume_dbfs = -50.0
max_segment_duration_s = 60.0
max_words_per_second = 8.0
ngram_sizes = (3, 4, 5, 6)
max_consecutive_ngram_repeats = 3
min_unique_token_ratio = 0.20
unique_ratio_min_tokens = 20
max_compression_ratio = 2.4
low_confidence_probability = 0.15
max_low_confidence_fraction = 0.50
min_confidence_word_count = 10
min_confidence_coverage_fraction = 0.80
retry_window_s = 15.0
retry_overlap_s = 0.5
```

Tests cover monotonicity/bounds, missing/duplicate/unexpected chunk results, legitimate measured silence, empty non-silent results, long segments, words/second, Russian repeated n-grams, low entropy, zlib compression ratio, nullable confidence, boundary deduplication, and clean text.

- [ ] **Step 2: Run tests and verify RED**

Expected: missing `audio_transcriber.quality`.

- [ ] **Step 3: Implement deterministic gates**

Tokenize with Unicode word matching and case-folding. Compression ratio is `len(utf8_text) / len(zlib.compress(utf8_text))`. Apply confidence failure only when the transcript has at least 10 words and at least 80% of them expose confidence; otherwise emit a `not_applicable` check. Compute the low-confidence fraction only over words with confidence. Coverage requires a one-to-one match between planned chunk IDs and result chunk IDs; a missing, duplicate, or unexpected result is an error. An existing empty result is accepted only when backend no-speech evidence meets the approved threshold or local `mean_volume_dbfs` is at most -50 dBFS. Every issue includes code, severity, exact interval, chunk IDs and safe evidence.

Emit one `QualityCheckResult` for every named gate even when it passes or is not applicable. Partition issue evidence into `warnings` and `unresolved_errors`, and derive report status from whether unresolved errors are empty. Stage 3 copies these fields losslessly into canonical JSON.

- [ ] **Step 4: Implement exactly one bounded recovery pass**

Map each error to affected chunk IDs, leave passing chunks untouched, split failing chunks into at most 15-second independent windows with 0.5-second overlap, and call retry with:

- no previous text or prompt;
- temperature 0;
- deterministic beam/search settings supported by the backend;
- pinned detected/configured language;
- mandatory word timestamps.

Merge replacement results, rerun every gate once, and return success only when no error-severity issue remains. Otherwise call `RunStateStore.record_failure` with exact unresolved intervals and raise `UnresolvedQualityError`; do not commit the quality stage.

- [ ] **Step 5: Verify retry behavior and commit**

Assert the retry callback receives only failing intervals and at most once. Run `test_quality.py` plus `test_asr.py`. Commit with `git commit -m "feat: block and recover ASR hallucinations"`.

---

## Stage 2 Completion Gate

Run:

```bash
export PLUGIN_ROOT="$PWD/plugins/transcribing-audio"
uv run --project "$PLUGIN_ROOT" pytest \
  "$PLUGIN_ROOT/tests/test_state.py" \
  "$PLUGIN_ROOT/tests/test_audio.py" \
  "$PLUGIN_ROOT/tests/test_asr.py" \
  "$PLUGIN_ROOT/tests/test_asr_local.py" \
  "$PLUGIN_ROOT/tests/test_asr_openai.py" \
  "$PLUGIN_ROOT/tests/test_quality.py" -q
uv run --project "$PLUGIN_ROOT" pyright --project "$PLUGIN_ROOT/pyproject.toml"
uvx ruff check "$PLUGIN_ROOT"
uvx ruff format --check "$PLUGIN_ROOT"
git diff --check
```

Expected: all default tests pass without network/model downloads; generated WAV exercises ffprobe/ffmpeg when available; repetition fixture triggers one isolated retry; unresolved retry creates failure evidence and no successful quality record.

Run `/simplify`, then walk and complete [the Stage 2 checklist](checklist-transcribing-audio-plugin-stage-2-asr.md). Review the full Stage 2 diff before Stage 3.
