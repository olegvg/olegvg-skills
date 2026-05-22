# Refresh Strategy

## Two operations, not one

The plugin separates **finding drift** from **resolving drift**:

- `/kb-check-drift` — read-only. Surfaces candidates for refresh. Never modifies `.kb/` or `.kb-state.json`.
- `/kb-refresh <path>` — write. Updates summaries and indexes affected by changes in `<path>`. Advances `.kb-state.json` to the current SHA.

Drift stays open until refresh is explicitly run. The agent never silently refreshes the KB.

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
- **Composable** — the user can invoke `/kb-refresh <path>` for just the area they care about, not the whole corpus.

## The drift-checker heuristic

`kb-check-drift` applies the following signals to `git log --stat <last_linted_sha>..HEAD` (plus a scan of `docs/plans/**` for decision-record candidates):

- New files above a threshold count (default: 5) in a single area → likely new subdomain.
- File renames or moves → index references stale.
- Changes to files referenced by existing indexes → summaries likely stale.
- New top-level directory → area structure may need a new index.
- Migration / schema files → semantic shifts likely; areas touching data are suspect.
- Deleted files referenced in `.kb/` → hard flag.
- Completed plan with no matching decision record in `.kb/decisions/` → recommend `/kb-record-decision`. Soft flag — not every plan yields a durable decision.

The heuristic is **policy, not code**. It lives in `skills/kb-check-drift/SKILL.md` as a checklist the agent applies. Users tune it by editing that file. That's the intended extension point — no configuration knobs, no YAML schema.

## State file

`.kb-state.json` stores:

```json
{
  "last_linted_sha": "<SHA>",
  "last_linted_at": "<ISO-8601 UTC>",
  "schema_version": 1
}
```

- `/kb-check-drift` reads this but does not write it.
- Only `/kb-refresh` writes it, and only after successful refresh. A refresh that fails halfway must not advance state.
- `schema_version` is loose intentionally — future versions may add per-area refresh timestamps.
