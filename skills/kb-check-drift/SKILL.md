---
name: kb-check-drift
description: Use when checking whether .kb/ is out of date with the corpus. Read-only. Applies heuristics to git log since the refresh watermark and returns refresh candidates. Triggers on "check drift", "is the kb stale", "что устарело в kb", "нужна ли синхронизация".
---

# kb-check-drift — Surface Refresh Candidates

## When to use

User wants to know whether the KB is stale without committing to a rewrite. Run this before a query to decide whether to trust the KB, or periodically to spot drift.

**Read-only.** This skill NEVER modifies `.kb/` content, summaries, indexes, or `.kb-state.json`. If changes are warranted, emit a list of refresh commands for the user to run.

The one exception: when invoked by `kb-maintain` or with `--write-artifact`, the skill writes an opt-in `.kb/.drift-report.json` so the downstream `kb-refresh` can reuse the diff/grep work. The artifact is ephemeral and recomputable — see [references/drift-report-artifact.md](references/drift-report-artifact.md).

## Input

- **`--write-artifact`** (optional) — write `.kb/.drift-report.json` after computing the report. Implied when invoked by `kb-maintain`.

## Workflow

### 1. Read state

Open `.kb/.kb-state.json`. Extract `last_linted_sha` and `last_linted_at`.

If missing: report "no KB state — build or refresh has never run". Do not proceed.

If `last_linted_sha == "no-git"`: report that drift check requires git. Stop.

### 2. Log the delta

Run:

```bash
git -C <corpus-root> log --stat <last_linted_sha>..HEAD
git -C <corpus-root> diff --name-status <last_linted_sha>..HEAD
```

Capture the list of changed files, rename/copy stats, deletions, additions, and commit messages.

### 3. Apply the heuristic

The heuristic is a checklist. **Tune it by editing this file.** The default checklist:

- **New files above threshold** — if a single directory or area saw ≥5 new files since last refresh, flag that area.
- **File renames or moves** — any rename under a directory referenced in `.kb/indexes/` is a flag. Index references are stale by definition.
- **Changes to files referenced by existing indexes** — grep `.kb/indexes/` for paths; if any flagged path appears, the index entry is suspect.
- **Changes to files referenced by existing summaries** — grep `.kb/summaries/` for paths; if any flagged path appears, the summary is suspect.
- **New top-level directory** — may mean a new area needs an index.
- **Migration / schema files** (e.g. `migrations/**`, `*.sql`, `schema.*`) — semantic shifts likely; any area touching data is suspect.
- **Deleted files referenced in `.kb/`** — hard flag. The KB points at something that no longer exists.
- **Completed plan with no decision record** — if a plan file under `docs/plans/` (or similar) has a sibling checklist with all items ticked, and no matching file exists in `.kb/decisions/` (match by slug), recommend `kb-record-decision <plan-path>`. Soft flag — not every plan yields a durable decision.

Tuning thresholds and signal rationale live in [references/heuristic.md](references/heuristic.md). Add or remove signals here as the user's corpus needs.

### 4. Report

Emit a structured report. Example shape:

```
Drift candidates (KB last refreshed at <timestamp>, SHA <short-sha>):

Area: billing
  Reason: 7 new files under src/billing/ (above threshold 5)
  Recommendation: /kb-refresh src/billing/

Area: auth
  Reason: src/auth/session.ts (referenced by .kb/summaries/auth/session.md) has changed
  Recommendation: /kb-refresh src/auth/

Hard flags:
  .kb/summaries/search/indexer.md references src/search/legacy.ts — file no longer exists.
  Recommendation: /kb-refresh src/search/

Decision candidates:
  docs/plans/2026-03-19-1400/plan-billing-rewrite.md — checklist ticked, no .kb/decisions/2026-03-billing-rewrite.md.
  Recommendation: /kb-record-decision docs/plans/2026-03-19-1400/plan-billing-rewrite.md
```

If no signals trip: report "no drift candidates. Last refresh at `<timestamp>` is current."

When multiple refresh candidates exist, recommend a **single batched call** in the report (e.g. `/kb-refresh src/billing/ src/auth/ src/search/`) — the refresh skill accepts multiple paths in one invocation and does one `git diff` plus one state advance. Sequential calls per path are wasteful.

### 5. Optionally write the artifact

If invoked with `--write-artifact` (or by `kb-maintain`), write `.kb/.drift-report.json` after step 4. Schema and lifecycle: [references/drift-report-artifact.md](references/drift-report-artifact.md).

Write atomically: write `.kb/.drift-report.json.tmp` first, then `mv` to the final name. The artifact must never be a partial file.

Users should add `.kb/.drift-report.json` to their corpus `.gitignore` — the artifact is ephemeral, recomputable from git history, and would cause merge conflicts otherwise.

### 6. Do NOT advance state

Do not touch `.kb/.kb-state.json`. Drift remains open until `kb-refresh` resolves it. That separation is the point of this skill.

## Discipline

- **Read-only against `.kb/` content, always.** Summaries, indexes, decisions, `.kb-state.json` — never written. The only write is the opt-in drift artifact.
- **Report, don't decide.** The user chooses whether to refresh. Do not run `kb-refresh` automatically even on a hard flag.
- **Heuristic is policy.** If it's misfiring on the user's corpus, propose an edit to this file or [references/heuristic.md](references/heuristic.md).
- **Batched recommendation by default.** When the report has multiple refresh candidates, suggest one `kb-refresh` call with all paths — not N separate calls.

## References

- Heuristic signals and tuning: [references/heuristic.md](references/heuristic.md)
- Drift report artifact schema: [references/drift-report-artifact.md](references/drift-report-artifact.md)
- Refresh strategy rationale: [docs/refresh-strategy.md](../../docs/refresh-strategy.md)
- Refresh: invoke the `kb-refresh` skill (or `/kb-refresh`).
