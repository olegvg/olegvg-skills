# The Three-Layer Knowledge Base Pattern

This plugin encodes a pattern for giving an agent navigable knowledge of a corpus (codebase, notes archive, docs folder) without blowing its context window.

See the [KB walkthrough](kb-workflow.md) for a first build and a complete
maintenance cycle. Read [Knowledge Base for Agents](https://www.linkedin.com/posts/ahaidukof_karpathy-%D1%84%D0%BE%D1%80%D0%BC%D0%B0%D0%BB%D0%B8%D0%B7%D0%BE%D0%B2%D0%B0%D0%BB-%D1%82%D0%BE-%D1%87%D1%82%D0%BE-%D0%BC%D1%8B-%D0%BD%D0%B0%D1%89%D1%83%D0%BF%D0%B0%D0%BB%D0%B8-activity-7446836637143130112-o920/)
for the original motivation.

## The layers

1. **Sources (Layer 1)** — the corpus itself. Code, notes, whatever the agent needs to reason about. Never duplicated inside `.kb/`.
2. **Summaries (Layer 2)** — prose explanations, one topic per file. Freeform size. Optional Mermaid diagrams. Live under `.kb/summaries/<area>/`.
3. **Indexes (Layer 3)** — navigation. Maximum 300 tokens per file. Signposts only, no prose content. Live under `.kb/indexes/`. Entry point is `.kb/indexes/_root.md`.

Alongside the three layers is a **decisions** store — distilled records extracted from completed plans, living under `.kb/decisions/`. Decisions are not a fourth layer: each record names the summaries it affects in its own `## Affected areas` block, and that backreference is the only link between a decision and a summary. The agent finds decisions for a summary by greping `.kb/decisions/` for the summary's path. Summaries themselves are not modified when a decision is recorded — they describe the present, decisions describe how the present was chosen.

## Why three layers

The agent has a finite context window. Naively dumping the corpus blows it. Naively dumping summaries still blows it on any corpus worth documenting. Naively dumping indexes is cheap but fails when the answer requires detail.

Three layers deliver progressive disclosure: the agent reads the map first (indexes), picks the right neighborhood (an area index), then descends to the relevant prose (summaries), and only opens sources if the summary points there. Context stays bounded.

## Why indexes-first

A cold-start agent doesn't know your corpus. If it starts by reading summaries, it reads wrong ones — expensive and slow. `_root.md` costs ≤300 tokens and orients correctly in one hop.

For decisions about a known summary, `kb-query --decisions-for` can go
directly to the decision records. Once the agent is inside a summary and sees a reference to a related summary, it may follow the link without returning to the index level. See [navigation-rules.md](navigation-rules.md).

## Why semantic grouping

Auto-doc tools group by directory. That fails because agents receive questions by task surface, not by filesystem layout. "Where are fees charged?" crosses three directories. The ingest skill groups summaries by **what a user would ask about them**, not by where the files sit on disk.

## Why manual refresh

Automatic doc regeneration on every commit produces two failure modes: stale docs (if refresh is slow) and irrelevant churn (if refresh is eager). Manual, trigger-based refresh with a separate read-only drift-checker gives the user explicit control. See [refresh-strategy.md](refresh-strategy.md).

## Summary stability contract

A summary survives normal edits to its source files only if its prose does not cite line numbers. Refresh costs scale with how much of the summary has to change when a source file is edited — and most edits shift line numbers without changing what the file *does*. The contract:

- **Reference code by symbol name in the body.** Functions, classes, modules, constants — by name in prose (`run_analysis`, `BillingService.refund`). Renames are caught by grep; line shifts are not events.
- **Pin precise line numbers only in `## References` at the end of the file.** Group them by symbol or section so a refresh can patch one block instead of rewriting paragraphs.
- **No inline `file.ext:123` citations in the body.** They become wrong the moment the next commit touches that file.

This is enforceable by convention, not by code. It is the single biggest determinant of refresh cost on a maturing corpus — when prose cites lines everywhere, refresh becomes a full rewrite; when prose cites symbols, refresh becomes a targeted patch on References. See [templates/summary.template.md](../skills/kb-build/templates/summary.template.md) for the shape.

## Why plans are excluded but decisions are included

Plans (`docs/plans/**` and similar timestamped journals) are operational artifacts: steps, drafts, abandoned branches, debate about alternatives. 90% of a plan's content is noise to anyone who didn't execute it. The build excludes plans by default to keep current-state summaries clear. See the
[build skill](../skills/kb-build/SKILL.md) for exclusions and overrides.

But a completed plan contains something that *is* durable knowledge: the decision made and its rationale. `/kb-record-decision` extracts that 10% — decision, context, rejected alternatives, consequences — into a standalone record in `.kb/decisions/`. A source plan can stay in the project's journal while the decision record serves as durable knowledge.

The query "how does X work now, and based on what decisions?" resolves via a single navigation: agent enters via `_root.md`, picks the relevant area index, reads the summary for X, then greps `.kb/decisions/` for that summary's path to find the records that shaped it. No separate "decisions" area to ambiguate routing — the decision is reached through the thing it affects, but the linkage lives in the decision record (in its `Affected areas` list), not in the summary.

This asymmetry is deliberate: a summary tracks the present and gets refreshed as code changes, while a decision is immutable history. Putting forward links in the summary would mean editing N summaries every time a cross-cutting decision is recorded, which is the single most expensive operation in `kb-record-decision`. The backreference lives in the immutable side; the mutable side stays untouched.

## The `.kb/` directory lives in the corpus, not in this plugin

Portability claim: a user should be able to copy `.kb/` between machines, check it into git with the code, version it alongside the sources. The plugin is stateless with respect to any specific corpus. This is non-negotiable — it's why the pattern survives the plugin.
