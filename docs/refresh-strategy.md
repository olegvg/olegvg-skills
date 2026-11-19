# Refresh Strategy

## Two operations, not one

The plugin separates **finding drift** from **resolving drift**:

- `kb-check-drift` surfaces candidates for refresh. With `--write-artifact` it
  also saves `.kb/.drift-report.json`. The refresh watermark stays unchanged.
- `/kb-refresh <path1> [<path2> ...]` — write. Updates summaries and indexes affected by changes in the approved path scope. Advances `.kb/.kb-state.json` to the current SHA unless invoked with `--no-advance-state`.

Drift stays open until refresh is explicitly run. The agent never silently refreshes the KB. A bare `/kb-refresh` is not a whole-corpus refresh: it first routes through `/kb-check-drift --write-artifact`, surfaces candidate paths, and waits for an approved scope.

## Why manual, not automated

### Against git-hook refresh

Running refresh on every commit:
- **Slow path** — refresh takes time; pre-commit hooks that take >5 seconds get disabled by contributors.
- **Noisy path** — most commits don't materially change the KB. Re-writing unchanged summaries produces diff churn without information.
- **Wrong path** — refresh needs the agent to read code carefully. A hook that greps for filenames and rewrites headers is worse than no refresh.

### Against scheduled refresh

Running refresh on a cron:
- **Timing mismatch** — drift accumulates by commit, not by wall clock. A low-commit week runs refresh for nothing; a high-commit week lets drift pile up.
- **Stale trigger** — by the time the schedule fires, the user has moved on from the code that drifted.

### For manual refresh with drift surfacing

- **Cheap to check** — `/kb-check-drift` is fast (git diff + heuristic). Run it before a query when you want confidence the KB is current.
- **Explicit gate** — refresh only runs when the user decides drift matters. No surprise rewrites.
- **Composable** — the user can invoke `/kb-refresh <path>` for just the area they care about, or pass several paths in one batched refresh.

## The drift-checker heuristic

`kb-check-drift` uses `git log --stat`, `git diff --name-status`, KB references
and completed plans to identify candidates between the watermark and HEAD.

- At least five new files in a single area by default → likely new subdomain.
- File renames or moves → index references stale.
- Area indexes pointing to affected or missing summaries → navigation may need repair.
- Changes to files referenced by existing summaries → summaries likely stale.
- New top-level directory → area structure may need a new index.
- Migration / schema files → semantic shifts likely; areas touching data are suspect.
- Deleted files referenced in `.kb/` → hard flag.
- Completed plan with no matching decision record in `.kb/decisions/` → recommend `/kb-record-decision`. Soft flag — not every plan yields a durable decision.

The agent applies a [heuristic checklist](../skills/kb-check-drift/references/heuristic.md)
and adapts its search patterns to the corpus.

## State file

`.kb/.kb-state.json` stores:

```json
{
  "last_linted_sha": "<SHA>",
  "last_linted_at": "<ISO-8601 UTC>",
  "schema_version": 1
}
```

- `/kb-check-drift` reads this but does not write it.
- `/kb-refresh` defaults its base SHA to `last_linted_sha`, unless `--base-sha <sha>` overrides the watermark.
- `kb-build` initializes the state with schema version 1. `kb-refresh` advances
  the corpus-wide watermark only after a successful refresh.
- Prefer one batch of approved paths. For separate refreshes in the same batch,
  keep the original base SHA and use `--no-advance-state` until the final
  successful refresh.

## Scope budget

`kb-refresh` is a scoped patching operation, not a rebuild. After diffing the approved path scope, it counts changed source files, total insertions+deletions, affected `.kb/summaries/**` files, and distinct KB areas touched.

- Below the soft thresholds, the main agent patches summaries inline.
- Between soft and hard thresholds, refresh dispatches one subagent per affected KB area and keeps index updates in the main agent.
- At or above a hard threshold, refresh stops and asks the user to narrow the scope or consider `kb-build` for an area that structurally changed.

This gate is part of the context-window contract: a refresh that crosses the hard budget becomes a partial rebuild and should not run in one main-agent pass.

## Optional drift artifact

With `--write-artifact`, including during `kb-maintain` discovery, the drift check
writes `.kb/.drift-report.json`. `kb-refresh` can reuse the file and reference lists
when HEAD and the base SHA match and the artifact covers the approved paths.
Refresh still reads the hunk evidence and counts needed for its scope budget.

The artifact is ephemeral and recomputable. Keep it out of Git and ignore it
when the stored SHAs or scope no longer match.

See [skills/kb-check-drift/references/drift-report-artifact.md](../skills/kb-check-drift/references/drift-report-artifact.md) for the schema and lifecycle.

## Batched refresh

`/kb-refresh` accepts **multiple paths in a single invocation** and prefers that form over N sequential calls. The drift report's recommendation is rendered as one batched call when multiple candidates exist:

```
Recommendation: /kb-refresh src/billing/ src/auth/ src/search/
```

This checks the union of the approved paths and advances the watermark once.
The [maintenance skill](../skills/kb-maintain/SKILL.md) uses the same batch
when refreshing explicit paths or paths selected from the drift report.
