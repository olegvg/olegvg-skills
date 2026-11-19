# Changelog

## [Unreleased]

## [0.10.1]

- Updated the installation, runtime, and maintainer guides. Removed superseded
  development plans and folded the lifecycle audit rationale into the
  [deep code review guide](docs/deep-code-review.md).
- Added a [KB walkthrough](docs/kb-workflow.md), documented all ten review
  methods, and explained when to use each skill in both READMEs.

## [0.10.0]

- Removed the standalone `audit-state-machines` skill. Its full audit guide
  and English and Russian trigger phrases are available through `deep-code-review`.

## [0.9.0]

- Added `deep-code-review` to `core-dev`. It reviews diffs and code paths using
  ten bundled guides, including the full implicit lifecycle audit.
  See the [review rationale](docs/deep-code-review.md).

## [0.8.0]

- Progressive-disclosure mobile-test-environments skill for Android, iOS/Device Hub and Appium, with non-starting device inventory and ownership-aware cleanup.
- `audit-state-machines` skill for reconstructing implicit lifecycles from code and reporting evidence, Mermaid diagrams and refactoring priorities. See the [design rationale](https://github.com/olegvg/olegvg-skills/blob/v0.8.0/docs/audit-state-machines.md).
- Deterministic full runtime and nine portable skill ZIPs (including five desktop-compatible skills), including every reference, skill-local template and MIT license.
- Validated portable/Codex/Claude metadata, group ownership and standalone references.
- Atomic builds, strict numeric release tags, Git-scoped notes and SHA256SUMS.
- Read-only CI/build jobs, pinned actions and a separate publication job.
- Package security/privacy documentation and local installer verification.
- Runtime-dependent audio skills excluded from generic skills CLI discovery.

## [0.7.0]

- Existing umbrella version; committed changes are listed from Git history by the release tooling.
