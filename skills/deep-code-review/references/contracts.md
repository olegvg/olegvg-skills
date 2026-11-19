# Contracts and counterexamples

Use this method when you can state what must hold for a class of inputs. A counterexample needs an admissible input, a reachable call, and an observable violation of the promise.

## Establish the obligations

For a diff, identify the promises affected by the changed rule. Inspect the callers, implementations, and input partitions needed to decide whether the change breaks them. For a full audit, inventory the operations in scope from the public entry points and their actual consumers. For each, record who supplies the input, what that caller must establish, and what every applicable implementation owes in return. Include distinct promises about failures and effects, such as leaving an existing document untouched after rejecting an edit.

Source each promise in a specification, a public interface, an assertion, or a caller whose correctness demonstrably depends on it. Record its applicability, including mode, configuration, or version if relevant. When two sources disagree, identify the affected caller and the decision needed to establish the intended rule. An implementation's current behavior alone cannot establish its own correctness.

## Look for a counterexample

1. Translate each promise into a predicate over inputs and observable outcomes. Follow the entry point through validation, dispatch, and return. Check where each caller establishes preconditions and where each implementation enforces the promised result.
2. Partition the supported domain by the predicates that select different behaviors. Try values on both sides of an inclusive bound, coincident endpoints, or equal ranking keys when those distinctions affect the result. Combine conditions when their overlap selects an earlier branch or bypasses a guard. Include invalid inputs if rejection is itself specified.
3. Reduce each candidate to the smallest reachable witness. For an editor that accepts half-open replacement ranges and promises insertion anywhere, replacing `[3,3)` in `abc` with `x` must yield `abcx`. Trace whether the public call reaches a guard that rejects start offsets equal to length. If the public entry point handles append first, that guard in the nonempty-range helper is harmless on this path. Check any other supported entry point before generalizing the conclusion.

## Build a decision table when rules interact

Use one row per reachable combination of conditions that affects the decision. For a diff, include overlapping rules and fallback cases whose outcome could change. For a full audit, cover the decision's reachable domain. Cite the constraint for any combination excluded as impossible.

| Conditions and witness | All matching rules | Required priority or combination | Expected action | Actual branch and action |
| --- | --- | --- | --- | --- |

Derive the expected action from the contract, then trace the implementation in evaluation order. Include a row where no rule matches if reachable, and record the specified default and the actual fallback. Check rows with multiple matches for conflicting actions or an earlier branch masking the required winner. Check uncovered combinations for a required action that falls through or a default that produces the wrong result. If the contract leaves priority or fallback unspecified, record the ambiguity. Use one distinguishing row as the regression assertion for each confirmed defect.

## Verify and report

Inspect the test assertions for the relevant input partition, expected result, error, and promised effects. A test that only checks success would miss an append that silently drops the inserted text. Cite the matching assertion or identify the exact missing or unverified observation.

Lead with proven violations and their contract source, minimal witness, expected and actual behavior, and responsible `file:line`. For a full audit, include a compact obligation ledger with each promise, applicable callers and implementations, partitions examined, assertion evidence, and verdict. Distinguish a violated promise, a candidate ruled out by a cited constraint, and a material unknown. Give the limits of sampled cases and name any unavailable route or conflicting requirement that restricts the conclusion.
