---
name: audit-state-machines
description: 'Use when reviewing implicit finite state machines, lifecycle transitions, or state split across flags, status fields, handlers, or layers. Triggers include "find implicit state machines", "audit state transitions", "найди неявные конечные автоматы", and "аудит переходов состояний".'
---

# Audit Implicit State Machines

Perform a read-only audit of the application or the requested part of it. Inventory the implicit finite state machines found within the reviewed scope. Look for entities or processes whose current state affects how later events are handled and whose transition rules must be reconstructed from code. Adapt the search and recommendations to the project's languages, frameworks, and conventions.

## Discover and reconstruct

1. **Set the scope.** Identify the modules, layers, and entry points in scope. Search for related flags, status fields, persistent values, and branches that depend on state. Follow event handlers, asynchronous callbacks, workers, timers, and persistence hooks where present. A stateless branch alone is only a search candidate.
2. **Trace the state.** For each candidate, follow initialization, restoration, and all identified writers through their callers and constraints. Record events, effective guards, state writes, and effects in execution order. Include failure, retry, and cancellation paths where applicable. Include relevant events that leave state unchanged and record whether they are ignored, rejected, or still cause effects.
3. **Model the lifecycle.** List states defined or implied by the code, including initial and terminal states where established. Derive joint states from related flags and model independent state dimensions separately. Identify representable combinations that violate an invariant. Distinguish states with a proven path, states ruled out by a constraint, and states whose reachability is unknown.
4. **Follow layer boundaries.** Trace a shared lifecycle end to end and identify the authoritative state and any derived or independently stored views. Record mappings and synchronization points between layers. Note unavailable adapters, configuration, or other paths that limit the audit.

## Verify findings

| Check | Evidence to include |
| --- | --- |
| Invalid combinations, missing recovery, unreachable states, or unintended dead ends | The invariant or expected behavior, its source, and a path or constraint that establishes the finding. Classify intended terminal states as part of the model. |
| Missing transition preconditions | The applicable precondition and whether each reachable entry point enforces it, including calls outside the usual flow. Check enforcement in downstream layers and data constraints. |
| Duplicate events, out-of-order results, races, or partial failures | The sequence or interleaving, the relevant reads, writes, and effects, and the violated invariant. Check retries, stale results, and what other components can observe after a partial failure. |
| Inconsistent state across layers | The mapping or synchronization step and a path on which the representations diverge. |
| Transition test coverage | Cite tests that assert the transition or relevant effect. Use `asserted`, `no assertion found in reviewed tests`, or `unverified`. A call alone does not establish coverage. |

Cite repository-relative `file:line` locations for findings and transition sites. Use requirements, tests, or enforced invariants as evidence of intended behavior. Mark inferred expectations as assumptions. Separate findings supported by the reviewed code from hypotheses and state what would resolve each material uncertainty.

## Report

1. **Summary.** List machines in risk order with purpose, highest-impact finding, and recommendation. State the areas reviewed and any gaps. Rank by impact and likelihood given the evidence for reachability. Report confidence separately.
2. **Details for each machine.** Give its name, purpose, state owner, state definitions, and invariants. Include a transition table with these columns.

   | From | Event | Guard or condition | To | Effects | Code evidence | Test coverage |
   | --- | --- | --- | --- | --- | --- | --- |

   Use one row per distinct transition or relevant event outcome. Cite each implementation site. Derive a Mermaid `stateDiagram-v2` diagram from the table using the same state and event names. Draw state changes and self-transitions with effects as edges. Keep ignored or rejected outcomes in the table. Split large diagrams by phase when useful and keep the complete table. List findings with their evidence and confidence.
3. **Refactoring priorities.** Give a brief recommendation for each machine, including whether an explicit model is warranted. Prefer the smallest change that protects the invariant. Consider a typed state representation, centralized transition logic, or a state-machine library when supported by the existing stack. Recommend guard, persistence, concurrency, or test changes where those address the underlying problem.
