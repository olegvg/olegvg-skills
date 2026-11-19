# Compatibility across versions

Audit whether supported versions can still exchange and interpret data as promised. For a diff, follow each changed contract from its producer to affected consumers. For a full audit, inventory versioned boundaries in the requested scope, including persisted records, files, APIs, events, and public client interfaces where relevant.

## Establish the version combinations

1. For each boundary, identify who writes and reads it, who controls their upgrades, and how long old data or client versions remain in use. Seek support policies, release artifacts, schema history, retention rules, migration ordering, feature gates, and rollback instructions. Obtain the old behavior from the supported version or a representative fixture. Identify any version whose implementation or deployment policy is unavailable.
2. Reconstruct the sequence of supported rollout stages. Include mixed application versions, schema expansion and backfill, activation of new writes, retirement of old readers, and rollback wherever applicable. When evidence establishes an atomic deployment or disallows rollback past a stage, use that constraint to bound the audit.
3. Build a reader/writer matrix. For each relevant stage, record the writing version, payload or storage shape, reading version, promised interpretation, actual result, and evidence that the pairing can occur. Cover old writes reaching new readers and new writes reaching old readers. Check request and response directions independently for two-way interfaces.

## Trace and verify behavior

- Select values that distinguish the contracts. Consider absent, null, or newly defaulted fields, enum extensions, renamed fields, units, precision, and identifiers as relevant. Follow a value through serialization, parsing, defaults, and the consumer's first observable use. If the contract includes a source-level API, inspect the supported caller's call site as well.
- Trace an old record or queued message through the new reader. Account for backlog, replay, and partially backfilled data. Trace a new value through any older reader that can return during rollback. If a consumer reads and rewrites data, check that it preserves fields or semantics its successor still needs.
- Try to rule out each apparent incompatibility. An older reader might reject a new status value, yet an enforced gate could keep all writers on the old vocabulary until older readers retire. Verify gate order, participating writers, and what happens to values already stored if rollback is permitted.
- Cite assertions that pair the actual versions or independent historical fixtures in the relevant direction. A current serializer round-tripping through its current parser establishes the current pairing only. Check the decoded business result or preserved data as well as successful parsing.

## Report

For a full audit, show the matrix and material gaps. For each defect, identify a permitted rollout stage, a concrete value, the source of the compatibility promise, and the resulting rejection, changed meaning, or data loss. Cite repository-relative `file:line` evidence for each available implementation and the constraint that permits the pairing. For a supported external client, identify the versioned artifact, documented behavior, or independent fixture used and which conclusion it supports. If the old client or deployment order is unknown, state which artifact would resolve the uncertainty. Recommend the smallest change that preserves the supported contract through the affected stage.
