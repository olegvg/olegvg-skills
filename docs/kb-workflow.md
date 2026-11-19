# Build and maintain a knowledge base with KB for Agents

Use this group when people repeatedly ask an agent how a project works, where
to change behavior, or why an earlier implementation was chosen. A new session
can start from a short map, read just the relevant summaries, and follow their
references to verify details. As the project changes, you can check which
summaries need attention and keep the reasons for shipped decisions searchable.

The KB lives in `.kb/` inside the codebase, notes archive, or documentation corpus
you select. The corpus remains the source of truth. Each area index stays within
300 tokens and points to one-topic summaries grouped by what people ask about.
Decision records sit alongside the summaries and link back to the topics they
explain. See the [three-layer pattern](concept.md) and [navigation rules](navigation-rules.md).

## A first pass through the workflow

The examples use a service with refund requests, workers, and a payment provider.
Run the skill invocations in an agent session opened at that service's root.
The Claude Code examples use the `kb-for-agents` plugin group. In the Codex
umbrella plugin, use names such as `$olegvg-skills:kb-build`. With a skill-only
install, ask the agent to use the installed skill by name.

### 1. Map an unfamiliar project with `kb-build`

Open the corpus root and run the build.

~~~text
/kb-for-agents:kb-build .
~~~

The build surveys the corpus, groups files by topic, and writes summaries and
indexes. A topic like “Refund retries” can span a route, a worker, and an adapter
even when those files live in different directories. The resulting KB may look
like this.

~~~text
.kb/
├── indexes/
│   ├── _root.md
│   └── billing.md
├── summaries/
│   └── billing/
│       ├── overview.md
│       └── refund-retries.md
├── decisions/
└── .kb-state.json
~~~

Start with the corpus you want to reuse across sessions. The build excludes
dated plans, generated output, and other scratch material by default. An
explicit `--include <path>` can bring in material normally excluded. The build
records the starting Git commit if available. It can also build a KB for a
non-Git corpus, where the watermark is `no-git`.

[Build workflow](../skills/kb-build/SKILL.md) ·
[Default exclusions](../skills/kb-build/references/default-exclusions.md) ·
[Manual templates](../templates/README.md)

### 2. Answer a project question with `kb-query`

~~~text
/kb-for-agents:kb-query Where is a refund retry scheduled, and how does it reuse the original provider request?
~~~

The agent reads `_root.md`, chooses the billing index, then opens the relevant
summary. From the summary it can follow source references to the worker,
provider adapter, or test assertion that supports the answer. It also looks
for decisions that name that summary in their affected-area list. A useful
answer gives the current behavior, source citations, and any gap in coverage.

This is a read-only workflow for onboarding, debugging, and questions across
module boundaries. If you already have a summary path and want its decision
history, use the direct lookup described below.

[Query workflow](../skills/kb-query/SKILL.md)

### 3. Find stale topics with `kb-check-drift`

After a change is committed, ask what parts of the KB may have drifted.

~~~text
/kb-for-agents:kb-check-drift
~~~

The check compares the recorded watermark with HEAD. It points out changed
source references, renames, deleted files, new areas, and possible decision
records. After a refund worker is moved, the report can name the old path in
the retry summary and recommend refreshing the relevant directories. A
candidate tells you where to look. The refresh establishes whether the prose
or links actually need edits.

The check leaves summaries, indexes, and the watermark untouched. Use
`--write-artifact` when another skill should reuse its structured results.

[Drift check](../skills/kb-check-drift/SKILL.md) ·
[Heuristic signals](../skills/kb-check-drift/references/heuristic.md)

### 4. Repair the affected summaries with `kb-refresh`

Choose the source paths that cover the approved update. For a retry change
that crossed billing and workers, pass both paths together.

~~~text
/kb-for-agents:kb-refresh src/billing/ src/workers/
~~~

Refresh follows the committed diff and updates affected text, references,
and index entries. For example, it can revise the explanation of retry
scheduling and replace a link to a worker that moved. The report names the
summaries and indexes updated and the resulting watermark.

The watermark covers the whole corpus. If you are completing one batch in
separate runs, use the same `--base-sha` for every run and keep
`--no-advance-state` set until the final successful refresh. Large changes may
need a narrower scope. See [refresh strategy](refresh-strategy.md) for scope
limits, state, and how a drift artifact is reused.

[Refresh workflow](../skills/kb-refresh/SKILL.md)

### 5. Preserve why a change shipped with `kb-record-decision`

Once a planned change ships, provide the path to its completed plan in your
project.

~~~text
/kb-for-agents:kb-record-decision planning/refund-retry.md
~~~

For example, a plan may explain why every attempt reuses the same
idempotency key for one refund and why per-attempt keys were rejected. The skill
checks that the work shipped, distills the decision, alternatives, and
consequences, and asks you to confirm which summaries it affects. It writes
one record under `.kb/decisions/`. The summary explains current behavior, and
the record preserves the rationale for choosing it.

Later, retrieve the record directly through the affected summary path.

~~~text
/kb-for-agents:kb-query --decisions-for .kb/summaries/billing/refund-retries.md
~~~

[Decision workflow](../skills/kb-record-decision/SKILL.md) ·
[Record format and example](../skills/kb-record-decision/references/decision-template.md)

### 6. Run a guided maintenance pass with `kb-maintain`

When you have merged several changes and have yet to decide what should be
refreshed or recorded, start with one invocation.

~~~text
/kb-for-agents:kb-maintain
~~~

The skill runs the drift check, saves its temporary report, and proposes
the refresh paths and completed plans worth reviewing. You choose the
updates. It batches approved paths into one refresh and delegates each
approved decision record to the decision skill. Its final report shows
the paths updated, records written, and final watermark.

If you already know the work, supply the source paths for a direct refresh
or `--record <completed-plan>` for decision recording. Keep the drift-only
skill for sessions where you want just an assessment.

[Maintenance workflow](../skills/kb-maintain/SKILL.md)
