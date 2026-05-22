---
name: kb-refresh
description: Use when synchronizing .kb/ with recent changes in one or more corpus paths. Reads git diff since the KB refresh watermark, updates affected summaries and indexes, advances .kb-state.json. Triggers on "refresh the kb", "sync the knowledge base", "update knowledge base", "обновить kb", "синхронизировать базу знаний".
---

# kb-refresh — Synchronize `.kb/` After Corpus Changes

## When to use

User invokes `/kb-refresh <path1> [<path2> ...]` after making changes to the corpus. Manual, targeted operation. Never automatic.

If the user did not specify any path, ask for one. Do not refresh the whole corpus by default — scope keeps the operation fast and reviewable.

## Input

- **One or more paths** — subdirectories or files within the corpus. Multi-path is the preferred form when several scopes need refreshing in the same pass; it does **one** `git diff` and **one** state advance over the union of paths.
- **`--base-sha <sha>`** (optional) — override the refresh watermark. Defaults to `.kb/.kb-state.json:last_linted_sha`. Used by the `kb-maintain` orchestrator to run a multi-call sequence against a single base.
- **`--no-advance-state`** (optional) — perform all the work but skip the final state write. Used by the orchestrator when chaining refresh with other writes; the orchestrator advances state once at the end.

## Workflow

### 1. Read state

Open `.kb/.kb-state.json`. Extract `last_linted_sha` unless `--base-sha` overrode it.

- If the file is missing: this is first build. Suggest invoking `kb-build` (or `/kb-build`) and stop.
- If `last_linted_sha == "no-git"`: refresh requires git. Stop.

See [references/failure-modes.md](references/failure-modes.md) for "base SHA not reachable from HEAD" and other recovery paths.

### 2. Reuse drift artifact when available

If `.kb/.drift-report.json` exists, and its `head_sha` matches `git rev-parse HEAD`, and its `base_sha` matches `<base_sha>`, reuse its pre-computed file lists. The drift skill already ran `git diff` and the `.kb/` greps; the artifact carries the results. Skip steps 3 and 4 and jump to step 5.

If the artifact is missing or stale, proceed with steps 3 and 4 normally. A stale artifact is not a warning — just ignore it.

### 3. Diff the path(s)

Run one combined diff over the union of input paths:

```bash
git -C <corpus-root> diff <base_sha>..HEAD -- <path1> <path2> ...
git -C <corpus-root> diff --name-status <base_sha>..HEAD -- <path1> <path2> ...
```

The first form shows content; the second gives the `M | A | D | R<NN> | C<NN>` file-status list. Identify:

- Changed files (modified content).
- Renamed files (old path → new path).
- Deleted files.
- New files in scope.

Exact commands and the multi-path batching rule are in [references/diff-and-grep-recipes.md](references/diff-and-grep-recipes.md).

### 4. Find affected summaries and indexes

Grep `.kb/summaries/` for references to each changed file path. Those summaries need review. Then grep `.kb/indexes/` for references to summaries that are themselves affected.

Use the batched `grep -F -f` recipe in [references/diff-and-grep-recipes.md](references/diff-and-grep-recipes.md) — reading each summary once regardless of how many changed files it references.

### 5. Update summaries

For each affected summary:

- Re-read the relevant sources (the changed files).
- Patch where content has shifted. Prefer targeted edits over full rewrites — the [summary stability contract in docs/concept.md](../../docs/concept.md) keeps line numbers in `## References` blocks so prose can stay unchanged when only line numbers shifted.
- Keep one-topic-per-file discipline. If a summary's scope has grown past one topic, split it and update the parent index.

### 6. Update indexes

If summaries were split, merged, added, or removed — update the area index. If an entire area disappeared or a new area emerged, update `_root.md`.

Enforce the 300-token index budget. Split or trim if violated.

### 7. Surface decision candidates

If the diff scope includes completed plans (`docs/plans/**` or similar) or commit messages point to a completed plan, check whether the corresponding `.kb/decisions/<YYYY-MM-slug>.md` exists.

- If a completed plan has no decision record, report it as a follow-up: invoke `kb-record-decision <plan-path>` (or `/kb-record-decision`).
- Do not create decision records inside `kb-refresh`; shipped decisions are captured by `kb-record-decision`.
- Do not block the refresh on soft decision candidates. Only block if the current summaries cannot be made accurate without resolving whether the plan shipped.

### 8. Advance state

Skip this step entirely if invoked with `--no-advance-state` — the orchestrator (`kb-maintain`) wants to advance once at the end of a chained pass.

Otherwise, rewrite `.kb/.kb-state.json`:

- `last_linted_sha` → current HEAD SHA: `git -C <corpus-root> rev-parse HEAD`.
- `last_linted_at` → current UTC ISO-8601 timestamp: `date -u +"%Y-%m-%dT%H:%M:%SZ"`.
- `schema_version` → unchanged.

### 9. Report

Summarize to the user:

- Path(s) refreshed.
- Files changed in the diff scope.
- Summaries updated (with paths).
- Indexes updated (with paths).
- Decision candidates found, if any, with `kb-record-decision <plan-path>` recommendations.
- State advanced to SHA `<new-sha>` — or "state NOT advanced (--no-advance-state)" when the orchestrator is chaining.

## Discipline

- **Scoped to the path argument(s).** Do not touch summaries for files outside the union of input scopes, even if you notice drift there. That's `kb-check-drift`'s job — it's the user's call whether to refresh those next.
- **Batch when possible.** Multiple scopes in one call beat N sequential calls. The contract is N paths in, one diff, one state advance.
- **State file is sacred.** Only advance `last_linted_sha` after summaries and indexes are actually updated. A refresh that fails halfway must not advance state. Skipped entirely under `--no-advance-state`.
- **Drift artifact is optional fuel, not a contract.** If it exists and matches, reuse it. If not, do the work yourself. Never warn the user about a stale artifact — silently ignore.
- **No automatic decision capture.** Decision records are historical knowledge and must be written by `kb-record-decision`, not opportunistically during refresh.

## Failure modes

See [references/failure-modes.md](references/failure-modes.md): state file missing, no-git corpus, base SHA unreachable, merge conflicts in scope, massive diff scope, summary spanning multiple areas, stale drift artifact, state write failure.

## References

- Diff and grep recipes: [references/diff-and-grep-recipes.md](references/diff-and-grep-recipes.md)
- Failure modes: [references/failure-modes.md](references/failure-modes.md)
- Pattern rationale: [docs/concept.md](../../docs/concept.md)
- Refresh rationale: [docs/refresh-strategy.md](../../docs/refresh-strategy.md)
- Drift-first pass: invoke the `kb-check-drift` skill (or `/kb-check-drift`).
