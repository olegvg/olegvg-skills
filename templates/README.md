# Templates — Manual Build

If you want to build `.kb/` by hand instead of running `/kb-build`, use the canonical files linked below. Build templates live inside `kb-build` so standalone installations include them.

## Minimum viable layout

```
<your-corpus>/.kb/
├── indexes/
│   └── _root.md
├── summaries/
├── decisions/
└── .kb-state.json
```

## Steps

1. Copy [_root.template.md](../skills/kb-build/templates/_root.template.md) to `.kb/indexes/_root.md`. Replace the placeholder areas with the real areas in your corpus.
2. For each area: copy [index.template.md](../skills/kb-build/templates/index.template.md) to `.kb/indexes/<area>.md`. Fill in the "when to enter" and leaves.
3. For each leaf: copy [summary.template.md](../skills/kb-build/templates/summary.template.md) to `.kb/summaries/<area>/<leaf>.md`. Write the prose.
4. Create an empty `.kb/decisions/` directory. Decision records land here when you run `/kb-record-decision` against a completed plan. You can also hand-author them using [decision.template.md](decision.template.md), but the skill is the expected path.
5. Copy [.kb-state.template.json](../skills/kb-build/templates/.kb-state.template.json) to `.kb/.kb-state.json`. Set `last_linted_sha` to the output of `git rev-parse HEAD`, or `no-git` for a corpus outside Git. Set `last_linted_at` to the current UTC ISO-8601 timestamp.

## Rules

- Index files are ≤300 tokens. Signposts, not content.
- Summary files: one topic per file. No size limit, but split if you're mixing unrelated concerns.
- `_root.md` is the first read for a question about the corpus. Keep it honest — if an area disappears, remove it from `_root.md`.
- `decisions/` is never referenced from `_root.md`. Each decision record names the summaries it shapes in its own `## Affected areas` block; agents find decisions for a given summary by greping `.kb/decisions/` for that summary's path. Summaries themselves never list decisions — the link lives in the immutable side.

## What to add to your corpus `.gitignore`

The drift checker may write an ephemeral artifact at `.kb/.drift-report.json` when invoked with `--write-artifact`, including during `kb-maintain` discovery. It is recomputable from git history and should not be committed:

```gitignore
# kb-for-agents drift artifact (ephemeral, recomputable)
.kb/.drift-report.json
```

Keep `.kb/.kb-state.json` **in** git — it is the refresh watermark and is meant to be shared between developers.
