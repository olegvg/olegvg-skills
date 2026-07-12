# Transcribing Audio Plugin Stage 2 Verification Checklist

## Deliverable Summary

Stage 2 adds private resumable run state, validated ffprobe/ffmpeg preparation, backend-neutral timestamped ASR, local MLX/faster-whisper implementations, consent-gated OpenAI transcription, overlap deduplication, hallucination gates and one bounded recovery pass.

## Run State

- [ ] Fingerprint covers canonical identity, sampled content, relevant config and runtime version.
- [ ] Credentials and control-only output flags are excluded.
- [ ] Run root is private, owned, symlink-safe and per-fingerprint locked.
- [ ] Stage commits validate, hash, fsync and atomically replace artifacts before manifest.
- [ ] Resume rejects missing, corrupt, hash-mismatched or schema-invalid stages.
- [ ] Interruption preserves completed stages and does not mark the active stage complete.
- [ ] Failure reports do not masquerade as successful stage records.

## Audio Preparation

- [ ] Missing ffmpeg/ffprobe fails before model/provider work.
- [ ] Original input remains byte-identical.
- [ ] Source identity is rechecked after normalization/chunk materialization to prevent TOCTOU reuse.
- [ ] Normalized copy is validated mono 16 kHz PCM.
- [ ] Chunk coverage/overlap is deterministic and bounded.
- [ ] OpenAI chunks remain below the documented/conservative byte ceiling.
- [ ] Spaces/Unicode in paths are safe argv elements.

## ASR Backends

- [ ] MLX/faster calls enable word timestamps and disable previous-text conditioning.
- [ ] CUDA/CPU compute settings match the approved compatibility matrix.
- [ ] Auto-detected language is persisted and pinned for later chunks/retry.
- [ ] OpenAI cannot run without an explicit consent value.
- [ ] Selected OpenAI model/format is verified from current official docs.
- [ ] Every backend emits the same mandatory word-timestamp contract.
- [ ] Overlap deduplication preserves chronological order and chunk provenance.
- [ ] No default test imports/downloads unavailable model runtimes or calls network.

## Quality and Recovery

- [ ] Versioned thresholds match the Stage 2 plan.
- [ ] Timestamp, planned-result bijection, silence, length, repetition, entropy, compression and confidence gates have positive/negative fixtures.
- [ ] Russian repetition-loop fixture fails.
- [ ] Missing/duplicate results fail; an empty result passes only with measured/backend silence evidence.
- [ ] Only failing chunks are retried.
- [ ] Retry uses smaller isolated windows, pinned language and no inherited prompt.
- [ ] A second failure records exact intervals, raises safely and blocks downstream output.

## Security and Verification Evidence

- [ ] Fixture secrets are absent from logs, repr, exceptions, manifests and subprocess argv.
- [ ] Focused pytest passes.
- [ ] Pyright strict passes.
- [ ] Ruff check/format pass.
- [ ] `git diff --check` passes.
- [ ] Stage diff is simplified and independently reviewed.

```text
pytest:
pyright:
ruff:
git diff --check:
OpenAI docs/model decision:
review findings:
```

## Stage Approval

- [ ] Stage 2 tasks have coherent semantic commits.
- [ ] No unresolved CRITICAL/HIGH finding remains.
- [ ] Stage 3 may begin.
