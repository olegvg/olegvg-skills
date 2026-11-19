# Default Exclusions

Paths the build skill never ingests by default. These are not knowledge — they are operational noise that muddles semantic grouping. The user can override individual paths with `--include <path>` when they genuinely want a normally-excluded path in the KB.

## The exclusion list

- `docs/plans/**` — dated planning artifacts. Their durable knowledge belongs in `.kb/decisions/` via `kb-record-decision`, not in summaries. Ingesting plans creates summaries that mix current state with historical intent.
- `docs/specs/**` — also dated planning artifacts. Same reasoning.
- `**/CHANGELOG.md` — git log is authoritative. A changelog summary duplicates git history with worse fidelity.
- `node_modules/**`, `.venv/**`, `vendor/**` — vendored dependencies. Their summaries belong to the upstream project, not the user's corpus.
- `target/**`, `build/**`, `dist/**`, `out/**` — build outputs. Regenerable, no durable knowledge.
- `.git/**` — version-control metadata. Use git commands, not summaries.
- `temp/**`, `tmp/**` — scratch directories by convention.
- Any directory whose name is a date or timestamp pattern at the corpus root (e.g., `2026-01-15-experiment/`, `20260115-data-pull/`). Dated top-level directories are usually scratch work.

## Why exclude plans but include decisions

Plans contain steps, drafts, abandoned branches, and the debate about alternatives. 90% of a plan's content is noise to anyone who didn't execute it. Summaries built from plans inherit that noise.

A completed plan does contain durable knowledge: the decision made and its rationale. `kb-record-decision` extracts that 10% into `.kb/decisions/`. The default build excludes plans. Decision records are stored separately in `.kb/decisions/` and linked to current-state summaries through each record's affected-area list.

## Overriding an exclusion

If the user has, say, an experimental notes archive at `temp/research/` that they want in the KB:

```
/kb-build . --include temp/research/
```

The override is per-build, not persistent. Override sparingly — every override increases the chance the build produces noise the user later asks "why is this in my KB?"

## Detecting timestamp-pattern directories

Match against these conservative patterns at the corpus root only (do not recurse, because timestamped subdirectories deeper in the tree are usually intentional):

- `^\d{4}-\d{2}-\d{2}` (e.g., `2026-01-15`)
- `^\d{8}` (e.g., `20260115`)
- `^\d{4}-\d{2}-\d{2}-\d{4}` (e.g., `2026-01-15-1430`)

If a directory at the corpus root matches one of these and the user has not passed `--include` for it, skip it. Mention in the build report which directories were skipped under this rule so the user can `--include` them if needed.
