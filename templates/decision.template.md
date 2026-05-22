# <YYYY-MM> — <decision slug>

**Decision.** One or two sentences. What was decided.

## Context

2–5 sentences describing the problem that made this decision necessary. Constraints, requirements, failure modes — why a choice was forced.

## Alternatives considered

- **<alt-1>** — one line on why rejected.
- **<alt-2>** — one line on why rejected.
- **<alt-3>** — one line on why rejected.

## Consequences

What changes as a result: code shape, process, follow-on obligations, trade-offs accepted.

## Affected areas

- `.kb/summaries/<area-a>/<leaf>.md`
- `.kb/summaries/<area-b>/<leaf>.md`

<!--
The Affected areas list is the ONLY linkage between this decision and the
summaries it shapes. Summaries themselves are never edited when a decision
is recorded — agents find decisions for a summary by greping .kb/decisions/
for that summary's path.

If a summary path here does not yet exist (the decision created a new area),
list the intended future path and flag it as a refresh follow-up.
-->

## Source plan

`docs/plans/<timestamp>/plan-<slug>.md`

<!-- Target 150–300 words total. Longer means it wasn't distilled. A record should stand alone — do not rely on the source plan still existing. -->
