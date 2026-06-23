# KB Pattern

Use this before changing `kb-*` behavior, KB templates, or KB rationale docs.

## Critical Invariant

`.kb/` lives inside the user's corpus, never inside this plugin. The plugin is stateless with respect to any specific corpus. A user must be able to copy `.kb/` between machines or check it into their own repo alongside their code.

## Three Layers

1. **Sources** — the corpus itself. Never duplicated.
2. **Summaries** (`.kb/summaries/<area>/*.md`) — prose, one topic per file, freeform size.
3. **Indexes** (`.kb/indexes/*.md`) — navigation, signposts only, no prose. Entry point: `.kb/indexes/_root.md`.

Indexes have a hard budget of **300 tokens per file**. If you relax that in a skill, update [../concept.md](../concept.md) and [../navigation-rules.md](../navigation-rules.md).

## Decisions

Decisions live in `.kb/decisions/*.md`. They are not a fourth layer and must not appear as a top-level area in `_root.md`.

The link between a decision and affected summaries lives in the decision record's `## Affected areas` block. Summaries themselves are not edited when a decision is recorded. Agents find decisions for a summary by greping `.kb/decisions/` for that summary path; `kb-query` performs this lookup automatically.

## Skill Contracts

| Skill | Mode | Writes `.kb/`? | Writes `.kb-state.json`? |
|---|---|---|---|
| `kb-build` | one-shot, fresh build | yes, creates | yes, initializes |
| `kb-query` | read-only | no | no |
| `kb-refresh` | scoped, manual | yes, updates | yes, advances `last_linted_sha` |
| `kb-check-drift` | read-only | no | no |
| `kb-record-decision` | manual, post-plan | yes, adds decision only | no |
| `kb-maintain` | orchestrated, manual | delegates only | delegates only |

The `kb-check-drift` / `kb-refresh` split is deliberate. Drift detection is read-only and reports candidates; only `kb-refresh` mutates and advances state. Never collapse them.

`kb-build` uses a strict three-pass workflow: survey, parallel subagent deep-build, then main-agent index assembly. The main agent never reads full file bodies in passes 1 or 3. Do not collapse those passes even on small corpora.

`kb-check-drift` heuristic policy lives in [../../skills/kb-check-drift/SKILL.md](../../skills/kb-check-drift/SKILL.md). Do not add config files or YAML schemas for it.

## Related Docs

- [../concept.md](../concept.md)
- [../navigation-rules.md](../navigation-rules.md)
- [../refresh-strategy.md](../refresh-strategy.md)
