# Behavioral equivalence

Use a differential comparison when two routes should agree on a defined observation. Establish the common domain and the equality rule before choosing examples. A discrepancy can establish disagreement even when neither route is a trusted reference.

## Choose the comparisons

For a diff, pair each affected behavior with its reference, alternate route, or previous revision. Focus on the inputs, histories, and observations the change could alter. For a full audit, inventory the equivalence promises throughout the named scope. Look for implementations behind the same interface and routes such as incremental versus clean, batch versus repeated single operations, or optimized versus reference. For each promise, identify every participating path, its selector and preconditions, and how it will be compared. Comparing several routes against one independently justified reference can cover the group.

Define agreement at the consumer boundary. Decide whether it includes returned values, error classes, persisted results, or the number and order of effects. Normalize only permitted variation. Comparing sets is valid for a unique unordered result but would hide duplicate emissions in an unordered stream that promises one emission per input.

## Run a paired investigation

1. Trace both paths from equivalent starting conditions in source or exercise them on isolated local fixtures. When executing stateful paths, give each an independent starting state. Hold relevant inputs, time, configuration, and dependencies fixed. Establish which selector admits each path and distinguish code-derived from observed results. A cache configured to bypass reads provides no evidence about its hit path.
2. Vary inputs where the algorithms differ, including the history that creates derived state. For a theme change, compare an incremental render after switching A to B with a clean render under B. A warm-cache test that never changes the theme exercises a different case. Reduce any disagreement to the shortest distinguishing input or history and locate the first implementation difference that explains the observable result.
3. Judge both outputs against an independent oracle such as a specification, a simple calculation, or a caller-visible invariant. Across revisions, identify intended changes and their exact domain. If a change explicitly adopts round-half-to-even, changing 2.5 from 3 to 2 satisfies the new contract. A difference between the revisions for input 2.4 still needs explanation. Shared helpers can make both paths agree on the same error.

## Verify and report

Check that tests assert the promised relation for the relevant conditions. For the theme case, inspect whether a test drives a cache hit and checks the resulting color against a fresh render or an independently expected value. A call count alone cannot settle color equivalence.

Lead with divergences, the paired inputs and observations, the comparison rule, and supporting `file:line` sites. When equality is required and the outputs differ, report the violation as confirmed. If the correct result is unknown, leave attribution and the choice of fix open. Identify the rule or independently established expected result that would settle the case. For a full audit, summarize each pair or reference group with its common domain, oracle, cases and histories checked, assertion evidence, and result. Distinguish intended differences, unexplained divergences, and agreement limited to the examined cases. Identify any missing selector, unavailable reference, or uncontrolled input that makes a comparison inconclusive.
