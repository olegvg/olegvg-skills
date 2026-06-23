---
name: simplify-code
description: Use when the user asks to simplify code, clean up a diff, reduce implementation complexity, remove duplication, improve reuse or efficiency, or run a portable /simplify-style pass without changing behavior. Triggers on "/simplify", "simplify this", "clean up this implementation", "упрости реализацию", "почисти код", "сократи сложность".
---

# simplify-code — Behavior-Preserving Cleanup

## Overview

Review changed code for concrete cleanup opportunities, then apply only fixes that preserve intended behavior. This is a portable version of Claude Code's `/simplify` workflow: reuse, simplification, efficiency, and altitude review before edits.

## Input

- Optional target: current diff, file path, branch, PR, commit range, or pasted code.
- Project instructions that govern the changed files.
- Existing tests or verification commands, when discoverable.

## Workflow

### 1. Establish Scope

Prefer the smallest review surface that matches the user's request.

- If the user passed a path, range, branch, PR, or pasted code, use that as scope.
- Otherwise review the current branch diff. Prefer `git diff @{upstream}...HEAD`, fall back to `git diff main...HEAD` or `git diff HEAD~1`.
- If there are uncommitted changes, or the range diff is empty, also include `git diff HEAD`.
- If the project is not git-backed, inspect the user-provided files or snippet.
- Read applicable project instructions for changed files before judging conventions or scope.

### 2. Review Four Cleanup Angles

Run the four angles independently. If the runtime supports subagents, run one pass per angle in parallel. If it does not, do four labeled passes yourself and keep findings separate until deduplication.

| Angle | Flag | Required evidence |
|---|---|---|
| Reuse | New code reimplements something already present in the codebase. | Name the existing helper, module, component, or pattern to reuse. |
| Simplification | Redundant or derivable state, copy-paste variants, deep nesting, dead code, needless abstraction, or tangled control flow. | Name the simpler form that preserves behavior. |
| Efficiency | Repeated computation, repeated I/O, independent work serialized, blocking work added to startup or hot paths, or long-lived closures capturing more scope than needed. | Name the cheaper alternative and the wasted work it removes. |
| Altitude | A fix is placed at the wrong depth, such as a brittle special case layered on shared infrastructure. | Name the underlying mechanism that should be generalized, or mark the improvement out of scope. |

Each finding must include: `file`, `line` if known, `angle`, one-line `summary`, concrete `cost`, and a behavior-preserving `proposed_fix`.

Do not surface style preferences, correctness bugs, speculative rewrites, or changes whose benefit is not tied to duplicated, wasted, or harder-to-maintain code.

### 3. Deduplicate and Gate

Merge findings that point to the same mechanism. Keep a finding only when all of these are true:

- The fix preserves intended behavior.
- The fix stays within the reviewed scope or touches only a small, necessary helper.
- The improvement has a concrete maintenance, reuse, or performance cost.
- The project already has enough context to implement it safely.

Skip findings that require product judgment, broad architecture work, unrelated refactors, or behavior changes. Note the skip briefly instead of arguing with it.

### 4. Apply Safe Fixes

Edit directly and narrowly. Prefer existing local helpers, existing naming, and existing patterns over new abstractions. Add an abstraction only when it removes real duplication or a repeated concept in the scoped change.

If a suspected cleanup exposes a correctness bug, do not fold it into the simplify pass. Report it separately and ask whether to switch into bug-fix or code-review mode.

### 5. Verify

Run the cheapest meaningful checks available:

- Focused tests for touched logic, when tests exist.
- Typecheck or lint when the repo exposes them and they are not excessively expensive.
- Formatter only when it is the repo's normal workflow.
- Manual diff review to confirm there is no behavior expansion.

If verification cannot run, say why.

## Safety Rules

- No behavior changes under a cleanup label.
- No broad rewrites unless the user explicitly asks for them.
- No unrelated files just because they are nearby.
- No new dependencies for cleanup-only work unless the project already uses them and the benefit is obvious.
- No "while here" bug fixes mixed into simplification.

## Final Report

Keep the final response short:

- What was simplified.
- What was skipped and why, if anything.
- Verification run and result.
