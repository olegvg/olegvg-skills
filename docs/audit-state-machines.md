# Audit State Machines Rationale

Applications often store lifecycle state in flags, status fields, or several layers.
A change can look valid at one write site while breaking an invariant established
elsewhere. The audit starts with events and follows the state they read and write.
This works across domains and languages because it follows behavior and ownership.

## Why reconstruct the lifecycle

A branch over an input can resemble a transition. A lifecycle carries state forward
and uses it to decide how a later event is handled. Related flags can form a joint
state, while independent values can be modeled separately. This keeps the inventory
small enough to inspect and preserves combinations that matter to the behavior.

Following effects in execution order matters even when a state value stays the
same. A repeated event can repeat an effect. A failed write can leave another
component observing a partial update. A late result can change newer state. When
the outcome depends on an adapter or configuration outside the reviewed scope,
the report records the condition and identifies the evidence still needed.

## Why the report is structured this way

The transition table is the record of observed behavior. File and line references
make guards, writes, and test assertions reviewable. The Mermaid diagram uses the
same states and events to make paths visible. The report gives reachability,
expected behavior, and confidence their own treatment so readers can distinguish a
confirmed defect from a hypothesis.

Risk ranks the impact and likelihood of a problem. The proposed change follows
the invariant that needs protection. A typed state model can help when transition
rules are scattered. A shared guard, an atomic write, or an assertion may be enough
when the failure has a narrower cause.
