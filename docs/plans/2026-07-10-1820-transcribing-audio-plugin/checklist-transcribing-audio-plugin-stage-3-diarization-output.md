# Transcribing Audio Plugin Stage 3 Verification Checklist

## Deliverable Summary

Stage 3 adds local pyannote diarization for exact/ranged/automatic speaker counts, deterministic word-level speaker alignment, safe post-alignment display names, canonical JSON validation, and readable TXT/SRT/VTT derivation.

## Diarization

- [x] Diarization is always local and uses no cloud diarization model.
- [x] Exact mode sends equal min/max and validates distinct raw-label count.
- [x] One-sided/two-sided ranges and automatic inference pass correct kwargs.
- [x] Model ID/revision and compute device are recorded.
- [x] MPS/CUDA/CPU diarization device is independent of ASR mode/backend.
- [x] HF token is absent from all logs/errors/artifacts.
- [x] Raw labels are not collapsed, enrolled or reused across recordings.
- [x] Default tests use fake pipeline and do not download models.

## Alignment and Naming

- [x] Greatest-overlap and exact tie-break rules have tests.
- [x] Nearest-speaker fallback and ties are deterministic.
- [x] Every ASR word has raw/display label and original provenance.
- [x] Empty diarization with non-empty ASR fails safely.
- [x] Speaker naming happens only after alignment.
- [x] Unknown, empty/control, or duplicate mappings fail.
- [x] Turn merge honors speaker changes and 1.5-second gap.
- [x] Cyrillic/Latin punctuation joining is deterministic.

## Canonical and Derived Outputs

- [x] JSON schema includes every design Output Contract field.
- [x] Speaker list comes from diarization and preserves exact labels even when one has no aligned word.
- [x] Word timestamps are mandatory and confidence is nullable.
- [x] Chronology, bounds, speakers, text and quality are validated.
- [x] Unresolved quality errors block canonical document success.
- [x] JSON is written/parsed before derived rendering.
- [x] TXT exact format uses `[HH:MM:SS–HH:MM:SS] SPEAKER: Text`.
- [x] SRT/VTT timestamps and cue structures parse.
- [x] Default output names match the design.

## Verification Evidence

- [x] Focused pytest passes.
- [x] Pyright strict passes.
- [x] Ruff check/format pass.
- [x] `git diff --check` passes.
- [x] Stage diff is simplified and independently reviewed.

```text
pytest: `test_models.py`, `test_diarization.py`, `test_alignment.py`, and
  `test_renderers.py`: 42 passed. Full plugin suite: 105 passed. Repository
  `make test`: 2271 passed, 40 skipped, 5 deselected.
pyright: Plugin strict check: 0 errors. Repository `uv run pyright` reports
  three pre-existing errors outside this stage in `psy_bot/jobs/reflect_cancellation.py`
  and `tests/api/test_ams_redact_endpoint.py`; neither file is changed here.
ruff: `uvx ruff check plugins/transcribing-audio` and
  `uvx ruff format --check plugins/transcribing-audio`: passed.
git diff --check: passed.
review findings: Independently rechecked all stage artifacts. No unresolved
  CRITICAL or HIGH finding in the Stage 3 diff.
```

## Stage Approval

- [x] Stage 3 tasks have coherent semantic commits.
- [x] No unresolved CRITICAL/HIGH finding remains.
- [x] Stage 4 may begin.
