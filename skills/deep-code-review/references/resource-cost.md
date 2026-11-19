# Resource ownership and cost

For a diff, start with the changed operation or ownership handoff. Trace one admissible workload through to its observable cost or cleanup. Include callers, overlapping work and configured limits where these can change the conclusion.

## Model the workload in a full audit

1. Inventory the in-scope entry points and workload shapes that consume the resource, including batch, scheduled, retry and cancellation paths where present. Identify competing users of a shared budget. For each materially different route, establish the unit of work, input dimensions and concurrency the caller permits.
2. Model total work per operation separately from peak live resources, queue growth and retention after completion. Put units on estimates. Trace batch sizes, fan-out, retry placement and cache behavior. State whether each bound is per request, worker, process or deployment. Cite the code or effective configuration enforcing it. Record unavailable capacity or traffic figures as unknown.
3. Trace each resource from acquisition through ownership transfers to release. Include partial initialization, early return, exception, timeout, caller cancellation and shutdown when reachable. If work continues after its caller exits, locate the new owner and the limit on its lifetime. Check cleanup during both normal completion and abandonment.

## Verify a cost or ownership claim

| Question | Evidence to seek |
| --- | --- |
| How much work can one request cause? | For N returned records with one downstream call each and at most A attempts for each call, the upper bound is N × A calls. Check whether the retry wraps a single item or the whole batch and whether the input limit is enforced before expensive work. Compare both versions on the same input when claiming a regression. |
| What can be live at the same time? | A sequential loop over ten items may use only one connection at a time. Check whether streaming materializes the input upstream, where concurrent requests meet the same pool, and what happens when capacity is reached. A bounded worker count can still leave the pending queue unbounded. |
| Can a resource outlive its owner? | Trace the acquired handle or retained object through its last release or reachable reference. Account for context managers, deferred cleanup and framework ownership. Show a reachable exit that bypasses cleanup and whether repeated operations compound retention. |
| Is the impact established? | A call-count increase can be proven from code. A latency regression needs comparable timings or other evidence linking work to elapsed time. A capacity breach can follow directly from proven demand and an enforced budget. For an unresolved claim, specify the workload, metric and comparison that could settle it, including input size, concurrency or cache state where they materially affect the result. Record measurement conditions and limits when measurements exist. |

## Report

For a full audit, list the workload paths, resource owners, cost or lifetime bounds, and where those bounds are enforced. Show the dominant term or unreleased resource for each finding, the input or exit that exposes it, the consequence, and the smallest change that addresses it. Cite repository-relative `file:line` evidence and tests that actually assert a call limit, peak occupancy, queue behavior or cleanup on the relevant path. Distinguish an observed measurement from a derived bound and a conditional impact. Identify unverified paths or absent assertions explicitly. For a diff, report the calculation or ownership trace needed to substantiate each finding.
