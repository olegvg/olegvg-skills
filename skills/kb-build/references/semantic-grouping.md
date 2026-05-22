# Semantic Grouping

Group files by **what a user would ask about them**, not by where they sit in the filesystem. This is the single most consequential decision in a build — wrong grouping produces a KB that mirrors `ls` and adds no navigational value.

## The rule

A domain is a set of files someone would want to understand **together** when working on a task. The files may live in three or four different directories on disk; what unifies them is that they answer one class of question.

## Good vs. bad groupings

| Good | Why |
|---|---|
| `auth` | Anyone asking about login flow / sessions / token rotation enters here. |
| `billing` | Pricing, refunds, fee calculation — one task surface. |
| `search-indexing` | Indexer, query parser, ranking — one pipeline. |
| `ops-runbooks` | On-call procedures, dashboards, alert wiring. |

| Bad | Why |
|---|---|
| `src` | A directory, not a domain. Nobody asks "tell me about src." |
| `tests` | Same — tests cut across every domain. |
| `utils` | "Utils" is the absence of grouping. Distribute or kill. |
| `scripts` | Filesystem artifact. Where the scripts run is the domain (`ops`, `dev-tools`, etc.). |

## A worked example

A `billing` domain may pull files from:

- `src/api/billing.ts` — HTTP routes.
- `src/db/billing_schema.sql` — schema.
- `src/services/refund.ts` — refund flow.
- `docs/billing-model.md` — pricing reference.
- `tests/billing.spec.ts` — tests.

Five files, four directories. They land in one summary area because anyone asking "where are refunds processed?" wants to read all five.

## Sizing

- **4–10 domains is typical.** Fewer than 3 means you are under-segmenting; more than 15 means you are over-segmenting (or the corpus is unusually large — re-check by reading the area indexes and asking "would I really want these as separate areas?").
- **Name each domain with a short kebab-case slug.** `auth`, `billing`, `search-indexing`. Not `Authentication and Authorization Services`.

## Symptoms of bad grouping

After the build, ask:

- **Does any area index list ≤2 leaves?** Probably a sub-area of another domain.
- **Does any area span obviously unrelated topics?** Split it.
- **Do summaries across different areas describe the same flow?** The flow is the domain — re-group.
- **Does the area set look like `ls src/`?** You grouped by directory. Re-group by task.

## When to abandon a candidate domain

If you started writing an area's overview and find yourself listing files without a unifying thread, the domain is not real. Move its files into adjacent domains. The KB does not need a "miscellaneous" area; if files cannot be placed, they probably belong in a summary that is one level coarser.

## How grouping interacts with Pass 1

The grouping decision happens in Pass 1, before any deep reading. You decide grouping based on file headers, README content, and directory layout — not on the full content of every file. This is intentional: deep reading would blow the main agent's context. A well-named file, a clear README section, and the import graph already tell you enough.

If you find yourself wanting to open file bodies to decide grouping, the grouping signal in the corpus is weak. Pick the best grouping you can on headers, and let Pass 2 surface refinements via the subagent briefs.
