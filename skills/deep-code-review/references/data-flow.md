# Data flow and representation

For a diff, start at the changed transformation. Choose a supported input sensitive to the changed transformation and trace it from a reachable producer to an observable consumer. Identify the first step that changes an obligation, or show how the relevant invariant is preserved. Bound any conclusion drawn from a single example. Follow sibling paths when they affect that conclusion.

## Reconstruct the flows in a full audit

1. Inventory the relevant outputs within the agreed scope, including returned values, exports and persisted projections. Work backward from each output to its authoritative inputs and forward from each input through the consumers in scope. Include alternate producers, fallback branches and reconverging paths. Group routes only where they share the transformation, contract and enforcement. Record unresolved origins or consumers.
2. Define what one field or row means at each boundary where its meaning could change. For a field, establish its origin, unit, encoding, precision and meaning when absent. For a collection, identify the unit being counted, its key, allowed multiplicity and any required ordering. Cite the consumer, schema or requirement that establishes each material invariant.
3. Carry a small labelled example through each distinct transformation or branch. Preserve source row IDs and intermediate values so another reviewer can tell where an item disappeared, appeared twice or changed meaning. Where sources merge, identify which value wins and whether an older or missing value can replace the authoritative one.

## Challenge the transformations

### Identity across bounded contexts

When a mapping crosses a domain boundary, write down what each side considers the same entity. Record who assigns each key, where it is unique, and how the producer's entity maps to the consumer's (one-to-one, many-to-one, or changing over time). Locate the translation in code. Matching field names and types establish only that the value can be passed.

Trace a pair of records that distinguishes the definitions. For example, maintenance identifies a physical meter by serial number, while billing identifies a service point that survives meter replacement. Carry two successive serial numbers for the same point through the adapter. A per-point billing history splits if it is keyed by serial number. Two maintenance records, one per meter, are correct for the same input. Report the first mapping that merges or splits identities contrary to the consumer's contract. If that contract is missing, identify the unresolved identity rule.

### Other transformation boundaries

| Boundary | Evidence to seek |
| --- | --- |
| Conversion, parsing or serialization | Try an input around the actual representation boundary. In `a😀b` the start of `b` is byte offset 5 in UTF-8 and offset 3 in UTF-16 code units. Trace the offset through to the consumer and check for an adapter that converts it. |
| Filter, join, grouping or deduplication | Trace unmatched keys and multiple matches where the schema permits them. Count rows per source identity before and after the operation. Two seats belonging to one account should contribute two to a seat count and one to a distinct-account count. A unique constraint may rule out a suspected fan-out. |
| Pagination, sorting or branching | Exercise tied ordering keys across a page boundary, empty results, or missing versus zero values where they take different branches. For a merge, trace a row that reaches both branches and one that reaches only one. Check the promised ordering, membership and cardinality at the final consumer. |

## Report

For a full audit, summarize the outputs and routes reviewed. For each materially different route, give its source, transformations, consumer, invariant and repository-relative `file:line` evidence. For a finding, show the smallest admissible input, its intermediate values at the first divergence, and the incorrect observable result. Cite test assertions that distinguish that result, such as exact IDs, multiplicity or unit. Mark missing assertions in the reviewed tests separately from tests you could not inspect. State which source or constraint would resolve each material gap. For a diff, report just the trace and evidence needed for the finding.
