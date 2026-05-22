---
name: kb-refresh
description: Use when synchronizing .kb/ with recent changes in a given corpus path. Reads git diff since the KB refresh watermark, updates affected summaries and indexes, advances .kb-state.json. Triggers on "refresh the kb", "sync the knowledge base", "update knowledge base", "обновить kb", "синхронизировать базу знаний".
---

# kb-refresh — Synchronize `.kb/` After Corpus Changes

## When to use

User invokes `/kb-refresh <path>` after making changes to the corpus. Manual, targeted operation. Never automatic.

If the user didn't specify a path, ask for one. Do not refresh the whole corpus by default — scope keeps the operation fast and reviewable.

## Input

- **Path** — a subdirectory or file within the corpus.

## Workflow

### 1. Read state

Open `.kb/.kb-state.json`. Extract `last_linted_sha`. This legacy field name is the refresh watermark.

If the file doesn't exist: this is first build. Suggest `/kb-build` instead, which builds the KB from scratch.

If `last_linted_sha == "no-git"`: tell the user the corpus is not a git repo and refresh cannot run. Stop.

### 2. Diff the path

Run:

```bash
git -C <corpus-root> diff <last_linted_sha>..HEAD -- <path>
```

Read the diff. Identify:
- Changed files (modified content).
- Renamed files (old path → new path).
- Deleted files.
- New files in scope.

### 3. Find affected summaries and indexes

- Grep `.kb/summaries/` for references to each changed file path. Those summaries need review.
- Grep `.kb/indexes/` for references to summaries that are themselves affected. Those indexes may need review.

### 4. Update summaries

For each affected summary:
- Re-read the relevant sources (the changed files).
- Rewrite the summary where content has shifted.
- Keep one-topic-per-file discipline. If a summary's scope has grown past one topic, split it and update the parent index.

### 5. Update indexes

If summaries were split, merged, added, or removed — update the area index. If an entire area disappeared or a new area emerged, update `_root.md`.

Enforce the 300-token index budget. Split or trim if violated.

### 6. Surface decision candidates

If the diff scope includes completed plans (`docs/plans/**` or similar) or commit messages point to a completed plan, check whether the corresponding `.kb/decisions/<YYYY-MM-slug>.md` exists.

- If a completed plan has no decision record, report it as a follow-up: `/kb-record-decision <plan-path>`.
- Do not create decision records inside `/kb-refresh`; shipped decisions are captured by `/kb-record-decision`.
- Do not block the refresh on soft decision candidates. Only block if the current summaries cannot be made accurate without resolving whether the plan shipped.

### 7. Advance state

Rewrite `.kb/.kb-state.json`:

- `last_linted_sha` → current HEAD SHA: `git -C <corpus-root> rev-parse HEAD`.
- `last_linted_at` → current UTC ISO-8601 timestamp: `date -u +"%Y-%m-%dT%H:%M:%SZ"`.
- `schema_version` → unchanged.

### 8. Report

Summarize to the user:
- Files changed in diff scope.
- Summaries updated (with paths).
- Indexes updated (with paths).
- Decision candidates found, if any, with `/kb-record-decision <plan-path>` recommendations.
- State advanced to SHA `<new-sha>`.

## Discipline

- **Scoped to the path argument.** Do not touch summaries for files outside `<path>`'s diff scope, even if you notice drift there. That's `/kb-check-drift`'s job — it's the user's call whether to refresh those next.
- **One commit-worthy change per invocation.** If the refresh turns massive, the plan should have been to split the path. Say so and ask the user to narrow scope.
- **State file is sacred.** Only advance `last_linted_sha` after summaries and indexes are actually updated. A refresh that fails halfway must not advance state.
- **No automatic decision capture.** Decision records are historical knowledge and must be written by `/kb-record-decision`, not opportunistically during refresh.

## Failure modes

- **`.kb/.kb-state.json` missing** → suggest `/kb-build`.
- **`last_linted_sha` not reachable from HEAD** (force-push, history rewrite) → ask the user how to recover. Safest recovery: treat the full history of `<path>` as diff scope, re-read, rewrite. Confirm before proceeding.
- **Merge conflicts in the diff** → the corpus has unresolved state. Ask user to resolve before refreshing.

## References

- Pattern: [docs/concept.md](../../docs/concept.md)
- Refresh rationale: [docs/refresh-strategy.md](../../docs/refresh-strategy.md)
- Drift-first pass: [skills/kb-check-drift/SKILL.md](../kb-check-drift/SKILL.md)
