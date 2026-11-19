---
name: deep-code-review
description: 'Use when the user requests a deep code review of a diff, PR, working tree, or named code path, or a focused audit of behavior, regressions, or implicit state machines. Triggers include "deep code review", "find implicit state machines", "audit state transitions", "глубокое ревью кода", "аудит поведения кода", "найди неявные конечные автоматы", and "аудит переходов состояний".'
---

# Deep code review

Review the requested scope read-only. Anchor the review in observable behavior and the repository's conventions. Use the requested report format when one is provided.

## Map the change before going deep

1. Establish the comparison. For a PR, use its intended base. For uncommitted work, include staged and unstaged changes and relevant new files. For a named path without a diff, identify its entry points. State any material uncertainty about scope.
2. Scan the whole requested change. For each distinct behavior, identify who relies on it and what must hold. Check callers, consumers, constraints, and test assertions where they establish the contract. Separate an intended change from a guarantee that should survive it.
3. Before following one lead, keep a short working list of concrete questions and the methods that could answer them. A single hunk may raise several independent questions. Select **all methods that answer distinct questions or supply missing evidence**. The presence of a cache, status, or queue alone is insufficient. Reuse evidence that settles multiple questions. A small change may be fully resolved by direct inspection.

## Choose methods independently

Use the observable signal to select the linked guide. Open each selected guide when investigating that question. In a diff review, follow the affected paths far enough to establish or rule out a regression. For an explicitly requested full audit, open its guide and use its inventory, verification, and report throughout the agreed scope, even when no diff is supplied.

| Signal in the change | Question and method |
| --- | --- |
| Eligibility, calculation, ranking, rule precedence, boundaries, or defaults change | Which admissible input or combination of conditions breaks the promised result? [Contracts and counterexamples](references/contracts.md) |
| A dependency crosses a module boundary, or a change exposes another module's internal decisions | Which boundary rule is violated, or which consumers must now change together? [Module boundaries and coupling](references/module-boundaries.md) |
| A value crosses representations or domain contexts, or records are filtered, joined, grouped, or paginated | Which value or identity is lost, duplicated, or reinterpreted? [Data flow and integrity](references/data-flow.md) |
| The change affects identity, access checks, resource selection, or what an actor can see or do | Which policy governs this actor, action, and resource at each entry point? [Access control](references/access-control.md) |
| Callbacks, workers, or requests overlap or wait on one another | Which reachable event order violates a guarantee or prevents progress? [Concurrency](references/concurrency.md) |
| A refactor, cache, optimization, or alternate implementation promises the same result | On what input do the two paths first diverge? [Behavioral equivalence](references/equivalence.md) |
| The shape or size of the input changes the amount of work or the lifetime of a resource | Which operation grows or holds a scarce resource, and by how much? [Resource use and cost](references/resource-cost.md) |
| An event's outcome depends on prior events or on state restored across calls | For a diff, trace the changed event from a reachable state through guards, writes, and effects. For an inventory or full transition audit, follow [Audit implicit state machines](references/lifecycles.md), including its verification and report. |
| A change affects the order, identity, or acknowledgement of durable writes, queued work, checkpoints, or external effects | What can be lost or repeated after interruption and replay? [Delivery and recovery](references/delivery.md) |
| Independently deployed readers and writers, old records, or in-flight messages meet a changed contract | Which supported combination fails during upgrade or rollback? [Version compatibility](references/compatibility.md) |

These signals are starting points. Follow a concrete concern outside the table as well. For example, a report refactor that adds a cache raises separate questions about output equivalence and cache visibility across users. A correct result for one user settles only the first question for that input.

## Verify and report

Use code smells as leads. Trace the suspected problem through the relevant audit and report it only when you can show a violated rule or a concrete cost of change.

- Return to the working list after each investigation. Add questions exposed by new evidence. Carry open questions and evidence into any handoff or resumed pass. Before finishing, resolve each applicable question with a finding, evidence ruling it out within scope, or a specific gap. Keep this bookkeeping internal unless the user requests coverage.
- For a finding, give a concrete witness such as a reachable input, event order, supported version or build, or dependency edge. Cite the governing contract or boundary rule and show the violation or impact. Check existing guards and downstream constraints. A missing test alone does not prove a defect. Use focused local checks when they can decide the question.
- Lead with actionable findings ordered by impact and reachability. Cite a precise repository-relative `file:line` and, for a diff, identify the change responsible. Merge duplicate explanations of the same defect. Separate pre-existing issues and material uncertainties from regressions.
- When no defect is substantiated, say so and identify any material unverified path. For a full audit, include the method's coverage inventory, rank findings by impact and reachability, and state confidence separately. Recommend the smallest correction the evidence supports. If a required equivalence is demonstrably broken but the correct result is unknown, keep the finding confirmed and leave the choice of fix open. Name the evidence needed to resolve material gaps. For a diff, include an inventory or diagram only when it helps explain the result.
