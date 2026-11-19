# Navigation Rules

## Cold-start rule: indexes-first

For a question about the corpus, start at `.kb/indexes/_root.md`. For a
decision lookup about a known summary, use `kb-query --decisions-for <summary-path>`.

This is enforced in the `kb-query` skill and observable in traces: every first-touch on a summary file should be preceded by reads on `_root.md` plus one or more area indexes.

## Warm-reference relaxation

Once the agent is working inside a summary (Layer 2), it may follow direct references to other summaries without returning to the index level.

Example: reading `summaries/auth/session.md` and finding a link to `summaries/billing/refunds.md` — the agent may jump straight there.

This relaxation is intentional. Strict indexes-only navigation would require the agent to re-enter through `_root.md` for every related concept — expensive and pedantic. The indexes earn their keep on cold start; once warm, references between summaries are cheap.

## Decisions: backreference, not forward link

Decisions live in `.kb/decisions/<YYYY-MM-slug>.md`. Each record names the summaries it shapes in its own `## Affected areas` block. **Summaries themselves are not edited when a decision is recorded** — they describe the present, decisions describe how the present was chosen.

When the agent is inside a summary and wants to know what decisions shaped it, the query is one grep:

```bash
rg -l -F -g '*.md' -- "<path-to-current-summary>" .kb/decisions/
```

This returns the list of records to read. The agent may follow those records freely under warm-reference relaxation — entering a decision through its summary is still a warm reference, just one that resolves via grep instead of an inline `[link]`.

`kb-query` performs this lookup automatically when reading a summary, so callers do not need to grep by hand — see the `--decisions-for` mode in that skill.

The query "how does X work now, and why was it built that way?" resolves: indexes → area index → summary for X → backreference grep into `.kb/decisions/` → read the records returned. Current state and historical rationale along one navigation path, with the linkage stored in the immutable side (decisions) rather than the mutable side (summaries).

## What the rules buy

- **Predictable context usage** — the upper bound on a cold-start query is `_root.md` + 1–3 area indexes (each ≤300 tokens) + a bounded number of summaries.
- **Debuggable navigation** — if the agent answers wrong, the trace shows whether it entered through `_root.md`, which areas it picked, which summaries it read. Fixing a bad answer often means fixing an index, not a summary.
- **Portable discipline** — the rules are stated, not implied. A new contributor can follow them without re-reading the full article.

## Anti-patterns

- **Dumping the whole `.kb/`** as initial context — defeats the point.
- **Skipping `_root.md` because "I know this corpus"** — the agent doesn't. Write for the agent.
- **Putting prose content in indexes** — indexes are signposts. If you catch yourself writing prose in an index file, it belongs in a summary.
