# Deep Code Review Rationale

A diff shows which lines changed. Understanding the behavior requires following
those lines to the entry points, consumers, constraints, and tests that define
what callers can rely on. Deep code review starts with that map and uses it to
decide which paths to investigate.

## Why the skill chooses methods by question

One change can affect several guarantees. A queued update, for example, can raise
a concurrency question about overlapping workers and a delivery question about
what happens after a committed write is replayed. Each guide asks for the
evidence that resolves its question. The reviewer can reuse evidence across
guides and open only those that apply to the requested scope.

A diff review follows affected paths until it can establish or rule out a
regression. An explicitly requested audit inventories the full agreed scope
using the relevant guide. The [lifecycle guide](../skills/deep-code-review/references/lifecycles.md)
includes the transition table, Mermaid diagram, and coverage checks for a full
implicit state-machine audit.

## What makes a finding actionable

A finding identifies the promise at stake, gives a reachable example that
violates it, and points to the code that causes the outcome. Test assertions,
guards, and downstream constraints can settle an apparent issue. Where a
supported configuration or a contract is missing, the review identifies the
evidence needed to reach a verdict. Findings are ordered by impact and
reachability so the reader can evaluate the smallest correction first.
