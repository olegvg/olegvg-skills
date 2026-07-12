# Transcribing Audio Plugin Stage 4 Verification Checklist

## Deliverable Summary

Stage 4 adds the safe interactive/non-interactive CLI, explicit OpenAI upload consent,
the resumable six-stage pipeline, local runtime health checks, and atomic final-output
publishing with rollback and journal recovery.

## CLI and Safety

- [x] Parser exposes the documented flags; `--speakers` is mutually exclusive with either range flag.
- [x] TTY runs always prompt for the input path, mode, and speaker policy; CLI values are prompt defaults only.
- [x] Non-TTY runs require both input and `--mode`; local mode rejects the cloud-upload flag.
- [x] Interactive OpenAI mode describes the upload and accepts only `y` / `yes`; the flag cannot bypass it.
- [x] Non-interactive OpenAI mode requires `--allow-cloud-upload` and creates explicit immutable consent.
- [x] Output storage, ffmpeg/ffprobe, Hugging Face access, OpenAI credentials, and provider capability checks occur before expensive processing.
- [x] Local pyannote and local ASR health checks run before normalization, ASR, or upload; OpenAI health checks remain local-only.
- [x] Exit handling covers configuration (2), prerequisite/storage (3), consent (4), provider/backend (5), unresolved quality (6), and interruption (130), with secret-redacted messages.

## Pipeline and Resume

- [x] All six committed stages use immutable DTOs and validated predecessors: inspect, ASR, quality, diarization, alignment, render.
- [x] OpenAI is confined to ASR; diarization remains local in every mode.
- [x] Valid resume records are reused; malformed diarization artifacts rebuild only diarization and downstream stages.
- [x] Same-fingerprint mutation is serialized by `RunStateStore.acquire()`.
- [x] Quality recovery remains bounded to one retry and blocks downstream output when unresolved.
- [x] `KeyboardInterrupt` reaches the CLI boundary, which returns 130 while preserving already committed stages.

## Final Publishing

- [x] Existing final targets fail without `--overwrite` and retain both contents and permissions.
- [x] Every staged output is validated before target mutation; targets, temporary payloads, and backups reject symlinks.
- [x] Output locks and journals are target-set scoped under the private runtime root; payloads/backups are same-filesystem files beside the targets.
- [x] A failure during the second output replacement restores every previous target; incomplete journals are recovered before a new publish.
- [x] Successful resume skips publishing when Stage 6 and final output digests already match.

## Verification Evidence

- [x] `uv run --project plugins/transcribing-audio pytest plugins/transcribing-audio/tests -q` — **115 passed**.
- [x] Pipeline integration uses deterministic backends for resume/corruption behavior and a real generated WAV with host ffmpeg/ffprobe for an offline local run.
- [x] `uv run --project plugins/transcribing-audio pyright --project plugins/transcribing-audio/pyproject.toml` — **0 errors, 0 warnings**.
- [x] `uvx ruff check plugins/transcribing-audio` and `uvx ruff format --check plugins/transcribing-audio` — passed.
- [x] `git diff --check` — passed.
- [x] `make test` — **2271 passed, 40 skipped, 5 deselected**.
- [x] Root `uvx ruff check` — passed.
- [!] Root `uv run pyright` has three pre-existing unrelated errors outside this plugin: `psy_bot/jobs/reflect_cancellation.py` and `tests/api/test_ams_redact_endpoint.py` (two).
- [x] Focused correctness/security review found and resolved the output-permission mutation and missing chunk/retry-directory defects; no Stage 4 CRITICAL/HIGH issue remains.

## Stage Approval

- [x] Stage 4 implementation and verification are complete.
- [x] Stage 5 may begin; its validation work should keep the noted root-Pyright baseline in mind.
