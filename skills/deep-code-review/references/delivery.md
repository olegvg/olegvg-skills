# Event delivery and recovery

Use this read-only review when an operation spans durable writes, messages, checkpoints, or external effects. For a diff, trace the changed handoff through its affected consumers. For a full audit, inventory every in-scope handoff, including each independently acknowledged recipient in a fan-out.

## Reconstruct the delivery contract

1. Start from business commands, scheduled jobs, publishers, and recovery or manual replay entry points. Trace from each initiating write to its intended outcome. Record what the contract promises about loss, duplication, order, or completion and where that expectation comes from. If the receiver or its contract is unavailable, name the limit on what can be established.
2. Map the transaction boundaries and durable facts along each route. Locate publication, acknowledgement, consumption, external effects, progress recording, and cleanup where applicable. Record what each acknowledgement confirms and which actor takes responsibility next. Distinguish the identity of the logical operation from message, attempt, and recipient identifiers.
3. Follow retry and replay through the implemented recovery paths. Identify who selects unfinished work, when it becomes eligible, how attempts end, and what happens to exhausted or quarantined work. For multi-stage processing, check that a saved checkpoint identifies an available artifact for the same inputs and that a later attempt is entitled to reuse it. Derive the ordering scope or deduplication lifetime from code, configuration, or the receiver's contract.

## Verify interruption and recovery

Start with an uninterrupted run where ordering or recipient selection is at issue. For recovery guarantees, reason about a hypothetical interruption between actions that commit independently. List the durable facts on each side, the next action after recovery, and the effects each recipient could observe. Cover accepted work with a lost acknowledgement, redelivery, and stale or out-of-order replay when reachable. For example, if a receipt is sent before recording completion, follow redelivery using the same business key. Trace the claim through worker loss and reassignment. Establish whether the effect and completion share a commit or the receiver honors a stable key for the full retry period. A broker acknowledgement alone cannot establish a downstream effect.

Cite tests that assert recovery from the relevant durable state, including how many effects occurred or which obligations remain pending. A successful publish or a mocked handler call establishes only that step.

## Report

For a diff, show the decisive delivery sequence or interruption and the resulting business effect. For a full audit, list each route, participants, stated guarantee, and durable handoffs. For each material failure window, tabulate interruption point, durable facts, next recovery action, recipient outcome, and code or test evidence. Record safeguards that rule out a suspected window and gaps such as an unavailable consumer or unknown retention setting. Cite repository-relative `file:line` locations. Rank substantiated findings by impact and reachability, separately from confidence in external assumptions.
