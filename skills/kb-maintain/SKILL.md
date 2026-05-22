---
name: kb-maintain
description: Use when the user wants a guided maintenance pass over .kb/ — check drift, choose refresh paths, and optionally record shipped decisions. Orchestrates kb-check-drift, kb-refresh, and kb-record-decision without hiding write boundaries. Triggers on "maintain the kb", "update and record decisions", "обслужить kb", "проверить и обновить базу знаний".
---

# kb-maintain — Guided KB Maintenance Flow

## When to use

User wants the KB brought current but has not specified whether the work is a drift check, a scoped refresh, decision recording, or a sequence of those operations.

This skill is an orchestrator. It does not implement refresh or decision-record logic directly; it delegates to the atomic skills and keeps each write boundary visible to the user.

## Input

- Optional scope path, e.g. `src/billing/`.
- Optional plan path, e.g. `docs/plans/2026-03-19-1400/plan-billing-rewrite.md`.
- Optional mode words like `check only`, `refresh`, `record decisions`, or `full`.

If the user's intent is ambiguous, ask one short clarification before writing anything.

## Workflow

### 1. Check state and drift

If `.kb/` does not exist, stop and suggest invoking the `kb-build` skill (or `/kb-build` if the user has the Claude Code plugin installed).

Invoke `kb-check-drift` first unless the user explicitly supplied a narrow path and asked to refresh it immediately. The drift report is read-only and gives the user a maintenance menu.

### 2. Propose an explicit maintenance plan

Turn the drift report into a short ordered plan:

1. Refresh candidates: invoke the `kb-refresh` skill with `<path>`.
2. Decision candidates: invoke the `kb-record-decision` skill with `<plan-path>`.
3. Any hard flags that should block work until the user resolves them.

Ask the user to approve the plan before invoking any writing skill.

### 3. Run approved refreshes

For each approved path, invoke the `kb-refresh` skill with `<path>` as input.

Rules:

- Preserve the scope chosen by the user.
- Do not collapse multiple unrelated paths into a whole-corpus refresh.
- If a refresh reports decision candidates, append them to the decision queue but do not record them automatically.

### 4. Run approved decision records

For each approved completed plan, invoke the `kb-record-decision` skill with `<plan-path>` as input.

Rules:

- Do not record decisions for incomplete plans.
- Do not advance `.kb/.kb-state.json` from this step.
- If `kb-record-decision` recommends a follow-up refresh, add it to the queue and ask before running it.

### 5. Final report

Report:

- Drift candidates reviewed.
- Refreshes run and final state SHA, if any refresh advanced it.
- Decision records written.
- Remaining suggested commands, if the user declined some work.

## Discipline

- **No hidden writes.** Every `.kb/` mutation must be attributable to either `kb-refresh` or `kb-record-decision`.
- **No automatic escalation.** A read-only drift check never turns into writes without user approval.
- **Do not merge atomic skills.** This orchestrator exists so `kb-refresh` and `kb-record-decision` can stay simple, auditable, and independently invokable.

## References

- Drift check: [skills/kb-check-drift/SKILL.md](../kb-check-drift/SKILL.md)
- Refresh: [skills/kb-refresh/SKILL.md](../kb-refresh/SKILL.md)
- Decision recording: [skills/kb-record-decision/SKILL.md](../kb-record-decision/SKILL.md)
- Refresh strategy: [docs/refresh-strategy.md](../../docs/refresh-strategy.md)
