# Concurrency and resource ownership

Use this read-only review when operations can overlap or completion depends on another participant making progress. For a diff, follow the changed synchronization or wait through the affected paths. For a full audit, cover all shared resources and waits discovered in the requested scope, including those protected by working guards.

## Discover participants and dependencies

1. Trace entry points that start competing or dependent work. Include requests, timers, manual triggers, callbacks, cancellation, and shutdown where applicable. Use code or configuration to establish which tasks, threads, processes, or replicas can run concurrently. Flag unknown deployment assumptions.
2. For each shared object, record its identity, readers and writers, invariant, and synchronization boundary. Identify every in-scope path to the critical operation, including paths that bypass the usual caller. Two locks bearing the same name can guard different instances. A database uniqueness constraint can protect writes from every process that uses that database.
3. For waits, record who holds the resource, what releases it, who can satisfy the condition, and which executor or permit that participant needs. Follow acquisition order, guard evaluation, reads, writes, wake-ups, and release, including failures and cancellation. A task waiting for work queued to its own single-worker executor can block progress on its own.

## Verify an interleaving

Establish a reachable initial state. Reduce the witness to the relevant steps that let participants observe stale data, violate an invariant, or block. For livelock or starvation, identify a repeatable cycle or unbounded schedule, the conditions that keep it possible, and any fairness guarantee that excludes it. A slow finite run alone cannot establish indefinite starvation. Cite the expected outcome and its source. Try to rule out the schedule using effective serialization, ownership, atomic updates, lock order, or predicate checks. For timeouts, cancellation, rollback, and retries, trace the actual caller-visible outcome. For example, opposite-direction transfers can acquire accounts in opposite order. Whether a caller loses a transfer depends on how the transaction abort and retry are handled.

Read the relevant tests. Identify how each establishes the competing operations or wait and which invariant, termination condition, or cleanup it asserts. A concurrent launch alone does not establish a particular schedule. State which schedules remain unverified.

## Report

For a diff, give the changed site, participants, ordered steps, and observed or code-derived consequence. For a full audit, inventory each resource or wait with participants, guard scope, code evidence, test assertions, and disposition. For each finding, give a short numbered schedule or one column per participant. Cite repository-relative `file:line` locations for entry points and decisive operations. Distinguish a reachable failure from a schedule excluded by a guard or dependent on missing configuration. Prioritize findings by impact and reachability and identify material coverage gaps.
