# Module boundaries and change propagation

Use this method when a change may expose an internal decision or make one module depend on another in a way the repository promises to prevent. For a diff, compare the base and changed dependency at its use site, then follow the affected consumers far enough to establish the consequence. For a full audit, inventory the modules, their public entry points, and the dependencies crossing their boundaries throughout the agreed scope.

## Map ownership and dependencies

1. For each boundary, establish which module owns the behavior or representation, what consumers may rely on, and what the owner can change independently. Look for package exports, build targets, public interfaces, architecture tests, documented rules, and supported consumers. Directory names and naming conventions can guide the search. Record any boundary whose intended contract is unclear.
2. Record each relevant dependency as consumer, provider, symbol or format used, and repository-relative `file:line`. For source dependencies, point the arrow from the module referencing a name to the module defining it. Trace re-exports and public signatures that expose an internal type. For dependencies on private formats, look beyond imports. A report that reads another module's storage key or interprets its database column depends on the owner of that representation.
3. Trace runtime dispatch separately where it could change the conclusion. A scheduler can call a storage adapter at runtime through a port declared by the scheduler. If the adapter imports that port and startup wires the two together, the adapter has the source dependency on the scheduler. Check whether a concrete adapter name also appears in scheduler code. Imports at the composition root, where implementations are selected and connected, may be exactly what the design requires.

## Test how a change propagates

- Choose a concrete change the owner is entitled to make while preserving the public contract. Use a change in the diff, two supported implementations, an existing migration, or a decision explicitly reserved to the owner. Trace which consumer must now change, where its build would fail, or which observable result would become incorrect.
- For example, suppose a store's API promises that a lookup returns a decoded record. A supported migration changes its private key prefix while preserving lookups through that API. If an exporter builds keys with the old prefix, trace a migrated record through the public lookup and through the exporter. Check for an alias or translation that still serves the exporter. If the published key format itself is a supported contract, reassess the premise.
- Check what the available tests prove. A dependency rule can establish a forbidden import. An isolated build can establish that an optional adapter has become mandatory. An exporter assertion over a migrated fixture can establish a missing record. A build that always includes every adapter and a mock that supplies already-decoded records leave those specific questions open.
- A new cycle or a widely imported helper warrants a closer look. Establish which repository rule the edge violates or which supported build, substitution, or owner-local change it prevents. Group indirect consumers only when the same dependency reaches them and imposes the same consequence.

## Report

For a diff, identify the introduced or widened dependency, cite the boundary promise and the use site, and show the smallest supported change or existing enforcement rule that demonstrates the impact. Distinguish pre-existing dependencies from regressions. For a full audit, summarize each boundary's owner, allowed surface, consumers, source or runtime direction where material, and evidence checked. Rank confirmed violations by their effect and reach. Identify any unresolved ownership, unavailable consumer, or unverified build variant and the evidence that would settle it.
