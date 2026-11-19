# Deep code review

Use [`deep-code-review`](../skills/deep-code-review/SKILL.md) when you need to
know whether a change breaks a guarantee someone relies on. The skill traces
changed lines through callers, consumers, data constraints, and tests. You get
a read-only review with concrete findings, the evidence for each one, and any
question that still depends on missing code, configuration, or a contract.

## Give the review a scope

- **Diff or PR.** Give the intended base and any behavior the change promises
  to preserve. For working-tree review, the skill includes staged and unstaged
  changes and relevant new files.
- **Named path.** Give a module, file, or entry point. The reviewer identifies
  its callers and follows the behavior in scope.
- **Full audit.** Name the property and the boundary you want covered. The
  reviewer inventories the applicable paths, guards, and tests throughout that
  scope, including paths where enforcement works.

In a Claude Code session with the `core-dev` group, for example, invoke
`/core-dev:deep-code-review Review this PR against main. Check retry behavior and rollback.`
In the Codex umbrella use `$olegvg-skills:deep-code-review` with the same request.
From a skill-only install, ask for `deep-code-review` by name.

## Methods and references

A diff review follows the changed behavior until it can establish or rule out
a regression. One change can affect several guarantees, and the reviewer opens
every guide that answers a distinct question. Each guide also defines what a
full audit should cover and report.

| Method | When to use it | How the review establishes a finding |
| --- | --- | --- |
| [Contracts and counterexamples](../skills/deep-code-review/references/contracts.md) | Eligibility, calculations, defaults, or rule precedence changed. | Establish what an entry point promises. Test boundary inputs and overlapping rules. Use a decision table for precedence and find the smallest reachable input whose actual result violates the promise. |
| [Module boundaries and change propagation](../skills/deep-code-review/references/module-boundaries.md) | A consumer starts depending on another module's internals, or a new dependency may prevent an independent change. | Map owners, public entry points, and static or runtime dependencies. Show a supported owner-local change that now forces a consumer to change, fails a supported build, or breaks an observable result. |
| [Data flow and representation](../skills/deep-code-review/references/data-flow.md) | Data crosses formats or contexts, or records are filtered, joined, grouped, ordered, or paginated. | Trace identity, values, units, order, and row counts from source to consumer. Find the first step that loses, duplicates, or reinterprets a value and the final result it changes. |
| [Access control and tenant isolation](../skills/deep-code-review/references/access-control.md) | A change affects identity, access checks, visibility, or resource selection. | Recover the actor, action, and resource policy. Trace effective identity and downstream enforcement at each relevant entry point. A full audit reports an authorization matrix with observed decisions and evidence. |
| [Concurrency and resource ownership](../skills/deep-code-review/references/concurrency.md) | Requests, callbacks, or workers can overlap or wait for one another. | Map participants, shared state, and the guards that actually apply across instances or processes. Give the shortest reachable schedule that violates an invariant or prevents progress. |
| [Behavioral equivalence](../skills/deep-code-review/references/equivalence.md) | A refactor, cache, optimization, or replacement promises equivalent behavior. | Compare both paths on the same supported input and history. Check returns, errors, and effects against the agreed comparison. Report the first divergence and the evidence needed to settle the expected result if it remains open. |
| [Resource ownership and cost](../skills/deep-code-review/references/resource-cost.md) | Cost changes with input size or a connection, worker, or other scarce resource stays live longer. | Establish the workload, limits, and resource lifetime. Use a call count, demand bound, concrete cleanup path, or comparable measurement to show the impact. |
| [Implicit state machines](../skills/deep-code-review/references/lifecycles.md) | The result of an event depends on earlier events or restored state. | Reconstruct the authoritative state, transitions, guards, effects, and test assertions. Follow stored and derived state across layers and check duplicates, cancellations, stale results, and invalid combinations. |
| [Event delivery and recovery](../skills/deep-code-review/references/delivery.md) | Durable writes, acknowledgements, checkpoints, queues, or external effects must survive interruption and replay. | Trace each handoff and what is durable at the point of failure. Follow retry or replay with the same logical operation and show which business effect is lost, repeated, or delayed. |
| [Compatibility across versions](../skills/deep-code-review/references/compatibility.md) | Old records, queued messages, or independently deployed readers and writers meet a changed contract. | Map supported rollout and rollback stages. Compare old and new readers and writers in both relevant directions. Show a legal version pairing and the first input it rejects or interprets differently. |

## Follow a change through several methods

Suppose a PR moves a refund retry into a worker.

- **Lifecycle** follows an eligible refund through scheduling, retry, and
  completion. It checks whether a delayed failure can change a completed refund.
- **Delivery** traces a provider success, a crash before recording it, and
  replay of the queued job. It checks whether replay uses the same provider key.
- **Concurrency** checks whether two workers can both claim the same refund.
  It traces the claim to the transaction or constraint that enforces ownership.
- **Compatibility** follows a job written before deployment into the new
  worker and checks whether rollback can read jobs written by the new version.

These traces can share evidence. A durable claim might settle the two-worker
scenario, while a crash after contacting the provider still requires a separate
replay trace. A focused review reports the confirmed consequences and the
material paths it could not verify.

## Run a full lifecycle audit

For a full implicit state-machine audit, give the skill a subsystem and ask for
its transitions, invariants, and coverage. For example, “Audit refund
lifecycles across the API, worker, and persistence layer. Include retries and
cancellation.”

A lifecycle carries state forward and uses it to decide how later events are
handled. Model related flags together and independent state dimensions
separately. Follow effects in execution order even when the stored state
stays the same. A repeated event can repeat an effect, and a late result can
overwrite newer state.

The audit reports each machine's owner, states, and invariants. Its transition
table shows the starting state, event, guard, resulting state, effects, code
evidence, and test coverage. An ignored event stays in the table, while a
repeated event with an effect also appears as a self-transition in the Mermaid
diagram. That diagram uses the same states and events so readers can trace
each path back to the evidence.

Rank findings by impact and likelihood given the evidence for reachability,
and state confidence separately. A shared guard or atomic write can protect
an invariant when the failure has a narrow cause.

## What makes a finding actionable

A finding identifies the promise at stake, gives a reachable example that
violates it, and points to the responsible change at `file:line`. It reports
the expected result, actual outcome, and smallest correction the evidence
supports. Test assertions, guards, and downstream constraints can settle an
apparent issue. Where a supported configuration or a contract is missing,
the review identifies the evidence needed to reach a verdict.

For example, if a replay uses a different provider key, the finding should
cite the promised one-refund behavior, the retry path that produces the new
key, and the provider contract that makes the second effect possible.
A regression check should assert the business outcome after replay, such as
the number of refunds, as well as the key passed to the provider.
