# Drift Report Artifact (`.kb/.drift-report.json`)

Optional structured output that `kb-check-drift` writes when invoked by `kb-maintain` (or with `--write-artifact`). It lets the downstream `kb-refresh` skip its own `git diff` and `.kb/` greps — the work has already been done.

This is **opt-in performance fuel**, not a contract. A user running `kb-check-drift` standalone for human inspection does not need the artifact and may suppress it.

## When to write

- Invoked by `kb-maintain` as part of a drift-then-refresh pass.
- Invoked with `--write-artifact` explicitly.

Do **not** write the artifact on a one-off human-facing drift check unless asked. The text report is the user surface; the JSON is only for chaining.

## Path

```
<corpus-root>/.kb/.drift-report.json
```

Inside `.kb/`, alongside `.kb-state.json`. Add `.kb/.drift-report.json` to the corpus `.gitignore` — the artifact is ephemeral, recomputable from git history, and would create merge conflicts between developers who run drift checks at different times.

## Schema

```json
{
  "base_sha": "<last_linted_sha>",
  "head_sha": "<git rev-parse HEAD>",
  "generated_at": "<UTC ISO-8601>",
  "changed_files": [
    "<path>",
    "..."
  ],
  "renames": [
    ["<old>", "<new>"],
    "..."
  ],
  "deletions": [
    "<path>",
    "..."
  ],
  "additions": [
    "<path>",
    "..."
  ],
  "affected_summaries": {
    "<changed-file>": [
      ".kb/summaries/<area>/<leaf>.md",
      "..."
    ]
  },
  "affected_indexes": [
    ".kb/indexes/<area>.md",
    "..."
  ],
  "decision_candidates": [
    {
      "plan_path": "docs/plans/<timestamp>/plan-<slug>.md",
      "checklist_path": "docs/plans/<timestamp>/checklist-<slug>.md",
      "checklist_complete": true,
      "expected_record_path": ".kb/decisions/<YYYY-MM>-<slug>.md",
      "record_exists": false
    }
  ],
  "schema_version": 1
}
```

## Consumer contract (kb-refresh)

`kb-refresh` reads the artifact and reuses its file lists **only if all three hold**:

1. `head_sha` equals current `git rev-parse HEAD`.
2. `base_sha` equals the refresh's base SHA (`.kb-state.json:last_linted_sha`, or `--base-sha` override).
3. The refresh's input paths are a subset of the file lists in the artifact (the artifact covers the whole drift scope; a narrower refresh just consumes the relevant subset).

If any condition fails, the consumer silently ignores the artifact and runs its own `git diff`. No warning — drift artifacts are ephemeral and may legitimately be stale (the user committed since the drift check).

## Producer rules

- Write the file **only after** the human-readable report is computed. The artifact and the report describe the same drift; if they diverge, the artifact is wrong by definition.
- Write atomically: write to `.kb/.drift-report.json.tmp`, then `mv` to the final name. This protects against partial writes when the producer is interrupted.
- Never write `decision_candidates[*].record_exists: true` without verifying the file exists on disk. Stale `true` values trick downstream skills into skipping a record that needs writing.

## Lifecycle

- Written by `kb-check-drift` (opt-in).
- Read by `kb-refresh` (opt-in, silently ignored if stale).
- Read by `kb-maintain` to produce the maintenance menu (when present, avoids re-running drift).
- Deleted by `kb-refresh` after a **successful** state advance — the artifact is now obsolete (head SHA moved). Optional: leave it and rely on the consumer's staleness check. Both behaviors are valid; the former is tidier.
- Never committed to git. Add to `.gitignore` in the user's corpus.

## Why JSON, not markdown

The human-readable report is markdown. The artifact is JSON because consumers parse it. Maintaining one source of truth in two formats is the producer's job — the report is for humans, the artifact is for skills. Do not invent a third format.
