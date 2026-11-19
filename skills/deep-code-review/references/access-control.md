# Access control and tenant isolation

Audit which actors may read, change, or delegate work on resources in scope. Use local source, checked-in policy, configuration, schemas, and test assertions. For a diff, start with the changed decision and follow its callers and effects. For a full audit, inventory the protected operations across the requested surface.

## Establish the policy and scope

1. Identify the protected resources, their owners, and the actions the application distinguishes. Read the policy or contract that gives these distinctions meaning. Record legitimate sharing, administration, and service roles. If the intended decision is inferred from existing code alone, label the inference.
2. Enumerate entry points from route registration, service interfaces, worker registrations, and export or bulk-operation definitions. Cross-check these against callers of the resource readers and writers. Group paths only where they share identity binding, enforcement, and observable effects.
3. Build an authorization matrix for materially different cases. Record the actual outcome as `allowed`, `denied`, or `undetermined` for each row. Cite the evidence for the outcome, or state what is missing. Use separate rows when the decision differs by action or field.

   | Actor and tenant | Action | Target and relationship | Expected decision (policy source) | Actual outcome | Entry point and enforcement site | Evidence or gap |
   | --- | --- | --- | --- | --- | --- | --- |

   Include both permitted and denied cases. An actor may be entitled to view a record while lacking permission to change it or see a particular field.

## Trace and verify decisions

- Establish how the application obtains actor identity, acting tenant, and any delegated authority. Follow those values to the point that selects data or commits an effect. For queued work, determine whose authority applies and whether policy requires a fresh membership check at execution.
- Follow the complete read or write path. For reads, inspect the selection of rows, fields, aggregates, and cached or exported results as applicable. For writes, identify which resource was authorized and which resource was actually changed. If a downstream service or database policy supplies the guard, verify its scope and the identity under which it runs.
- Try to rule out apparent mismatches from local evidence. A handler that loads an invoice by ID can be correctly scoped if all its reachable paths use a tenant-bound repository and the query enforces that tenant. Conversely, a filter that hides invoices from a list establishes only the list behavior. Check separately how an authorized user reaches an individual invoice.
- Cite test assertions for the observable decision. For example, a cross-tenant listing test can assert that the other tenant's record is absent while the caller's own record remains visible. A rejected write can assert that the protected value and any promised side effects remain unchanged. Identify mocked or unexercised enforcement layers.

## Report

For a full audit, show the matrix, covering shared enforcement once with its applicable entry points. For each finding, cite the policy, reachable code path, and the returned data, denied capability, or committed effect at repository-relative `file:line` locations. Distinguish supported violations from unresolved cases such as missing deployment policy. Name the smallest correction or missing piece of evidence and keep the investigation local and read-only.
