---
name: kb-refresh
description: Use when synchronizing .kb/ with recent changes in one or more corpus paths. Reads git diff since the KB refresh watermark, updates affected summaries and indexes, advances .kb-state.json. Triggers on "refresh the kb", "sync the knowledge base", "update knowledge base", "обновить kb", "синхронизировать базу знаний".
---

# kb-refresh — Synchronize `.kb/` After Corpus Changes

## When to use

User invokes `/kb-refresh <path1> [<path2> ...]` after making changes to the corpus. Manual, targeted operation. Never automatic.

If the user did not specify any path, **do not infer the scope from `git status` or pick "the whole corpus" silently** — even in non-interactive / auto modes. Either ask, or invoke `kb-check-drift` first (see step 0 below) and propose specific paths. A bare refresh against the whole corpus is the most expensive form of this skill and almost never what the user wants.

## Input

- **One or more paths** — subdirectories or files within the corpus. Multi-path is the preferred form when several scopes need refreshing in the same pass; it does **one** `git diff` and **one** state advance over the union of paths.
- **`--base-sha <sha>`** (optional) — override the refresh watermark. Defaults to `.kb/.kb-state.json:last_linted_sha`. Used by the `kb-maintain` orchestrator to run a multi-call sequence against a single base.
- **`--no-advance-state`** (optional) — perform all the work but skip the final state write. Used by the orchestrator when chaining refresh with other writes; the orchestrator advances state once at the end.

## Scope budget (hard gates)

These limits exist to keep the main agent's context bounded. Check them after step 3 (diff). If a gate trips, switch flow as instructed — do **not** plow ahead in the main context.

| Signal | Soft threshold | Hard threshold |
|---|---:|---:|
| Changed source files (excluding `.kb/`) | 15 | 25 |
| Diff insertions+deletions across scope | 1500 lines | 3000 lines |
| `.kb/summaries/**` files needing edits | 8 | 15 |
| Distinct KB areas touched | 3 | 5 |

- **Below soft threshold**: proceed inline (steps 5–8).
- **Between soft and hard threshold**: switch to multi-area subagent dispatch (step 5b). Do not attempt inline patching.
- **At or above hard threshold**: STOP. Report the count and ask the user to narrow scope (split `<path>` into subpaths and re-invoke per area), or to run `kb-build` for the affected area if it has structurally changed.

The thresholds are calibrated to "one main-agent context window can hold the diff, the relevant summaries, and the edits to them without compaction." Cross any of them and the refresh is no longer a refresh — it is a partial rebuild.

## Workflow

### 0. Resolve scope (when no path was given)

If the user invoked `/kb-refresh` with no path argument, do **not** infer scope from `git status`, `git log`, or "everything since the watermark". Instead:

1. Invoke `kb-check-drift` with `--write-artifact` (read-only; writes `.kb/.drift-report.json` but no other `.kb/` mutation).
2. Present the drift report's grouped refresh candidates to the user.
3. Ask which candidate paths to refresh. Accept a multi-path answer.
4. Continue with step 1 using the approved path list. The artifact written in 0.1 will be reused in step 2.

If the user has already approved a path list (e.g. via `kb-maintain` orchestration), skip step 0 entirely.

### 1. Read state

Open `.kb/.kb-state.json`. Extract `last_linted_sha` unless `--base-sha` overrode it.

- If the file is missing: this is first build. Suggest invoking `kb-build` (or `/kb-build`) and stop.
- If `last_linted_sha == "no-git"`: refresh requires git. Stop.

See [references/failure-modes.md](references/failure-modes.md) for "base SHA not reachable from HEAD" and other recovery paths.

### 2. Reuse drift artifact when available

If `.kb/.drift-report.json` exists, and its `head_sha` matches `git rev-parse HEAD`, and its `base_sha` matches `<base_sha>`, reuse its pre-computed file lists. The drift skill already ran `git diff` and the `.kb/` greps; the artifact carries the results. Skip steps 3 and 4 and jump to step 4.5.

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

### 4.5. Check scope budget

Count: changed source files, total insertions+deletions, affected `.kb/summaries/**` files, distinct KB areas touched (an "area" is a top-level subdirectory under `.kb/summaries/`).

Compare against the **Scope budget** table above. Then branch:

- **Below soft threshold** → step 5a (inline patching by main agent).
- **Between soft and hard threshold** → step 5b (multi-area subagent dispatch).
- **At or above hard threshold** → STOP. Print the counts and which threshold tripped. Ask the user to narrow scope (e.g. `<path1>/<sub1>` and `<path1>/<sub2>` separately instead of `<path1>` as a whole), or to consider `kb-build <area>` for areas that have structurally changed (new modules, new top-level concepts).

Do not silently proceed past a hard threshold. Crossing it is the failure mode that produces "refresh ran for hours and ate the context window".

### 5a. Update summaries inline (small scope)

For each affected summary, work in this order:

1. **Read the diff hunks first**, not the full file. Use `git -C <corpus-root> diff <base_sha>..HEAD -- <source_file>` to see exactly what changed. Most refresh edits can be made from the diff alone — symbol renames, new fields, removed flags, changed defaults are all visible in the hunk.
2. Open the full source file **only when** you need to verify a specific line number for the summary's `## References` block, or when the diff context is too thin to understand the change. Do not pre-open all changed files "to ground updates" — that is the failure mode that blows the context budget.
3. Patch the summary with surgical `Edit` calls. Prefer targeted edits over full rewrites — the [summary stability contract in docs/concept.md](https://github.com/olegvg/olegvg-skills/blob/master/docs/concept.md) keeps line numbers in `## References` blocks so prose can stay unchanged when only line numbers shifted.
4. Keep one-topic-per-file discipline. If a summary's scope has grown past one topic, split it and update the parent index. If a new topic deserves its own summary (e.g. a new module that does not fit any existing leaf), write a new summary file rather than overloading an existing one.

### 5b. Update summaries via subagent dispatch (multi-area scope)

When the scope budget puts you between soft and hard thresholds, do **not** patch all summaries in the main context. Dispatch one subagent per affected KB area (the same area = one top-level `.kb/summaries/<area>/` directory).

Use the prompt shape and contract in [references/subagent-dispatch.md](references/subagent-dispatch.md). Key contract points:

- Each subagent receives: the area name, the list of changed source files relevant to that area (from step 3), the list of `.kb/summaries/<area>/*.md` files to review (from step 4), and the `<base_sha>` for diff lookup.
- Subagent reads the diff hunks itself and patches the area's summaries. It **does not** write to `.kb/indexes/` — index updates stay in the main agent.
- Subagent returns a ≤200-word brief: summaries patched, summaries added, summaries split, suggested index updates.

Dispatch in parallel where the host supports it. The main agent holds only the briefs returned, not file contents — same context-window guarantee as `kb-build` Pass 2.

### 6. Update indexes

Main agent only — never delegate index writes to a subagent. Indexes are global and need the full brief set.

If summaries were split, merged, added, or removed (whether by step 5a or by subagent briefs from 5b) — update the affected area index. If an entire area disappeared or a new area emerged, update `_root.md`.

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

- **Scope budget is a hard gate, not a suggestion.** If the diff exceeds the hard threshold in step 4.5, stop and ask the user to narrow scope. A refresh that exceeds budget produces summaries that match neither the old nor the new code well, because the main agent runs out of context.
- **Bare invocation is never whole-corpus.** With no path argument, route through `kb-check-drift` (step 0). Inferring scope from `git status` or "everything since the watermark" is the most expensive mistake this skill can make.
- **Read diffs before files.** Step 5a opens full source files only to verify `## References` line numbers. Pre-opening every changed file "to ground updates" is the failure mode that triggers usage-limit termination.
- **Dispatch when multi-area.** Step 5b uses subagents the same way `kb-build` Pass 2 does — and for the same reason. Do not patch summaries across 4+ areas in the main context.
- **Scoped to the path argument(s).** Do not touch summaries for files outside the union of input scopes, even if you notice drift there. That's `kb-check-drift`'s job — it's the user's call whether to refresh those next.
- **Batch when possible.** Multiple scopes in one call beat N sequential calls. The contract is N paths in, one diff, one state advance.
- **State file is sacred.** Only advance `last_linted_sha` after summaries and indexes are actually updated. A refresh that fails halfway must not advance state. Skipped entirely under `--no-advance-state`.
- **Drift artifact is optional fuel, not a contract.** If it exists and matches, reuse it. If not, do the work yourself. Never warn the user about a stale artifact — silently ignore.
- **No automatic decision capture.** Decision records are historical knowledge and must be written by `kb-record-decision`, not opportunistically during refresh.

## Failure modes

See [references/failure-modes.md](references/failure-modes.md): state file missing, no-git corpus, base SHA unreachable, merge conflicts in scope, scope-budget exceeded (the hard-gate version of "massive diff"), bare invocation with no scope, summary spanning multiple areas, stale drift artifact, state write failure.

## References

- Diff and grep recipes: [references/diff-and-grep-recipes.md](references/diff-and-grep-recipes.md)
- Subagent dispatch contract for multi-area refresh: [references/subagent-dispatch.md](references/subagent-dispatch.md)
- Failure modes: [references/failure-modes.md](references/failure-modes.md)
- Pattern rationale: [docs/concept.md](https://github.com/olegvg/olegvg-skills/blob/master/docs/concept.md)
- Refresh rationale: [docs/refresh-strategy.md](https://github.com/olegvg/olegvg-skills/blob/master/docs/refresh-strategy.md)
- Drift-first pass: invoke the `kb-check-drift` skill (or `/kb-check-drift`).
