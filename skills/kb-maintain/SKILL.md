---
name: kb-maintain
description: Use when the user wants a guided maintenance pass over .kb/ — check drift, choose refresh paths, and optionally record shipped decisions. Orchestrates kb-check-drift, kb-refresh, and kb-record-decision without hiding write boundaries. Triggers on "maintain the kb", "update and record decisions", "обслужить kb", "проверить и обновить базу знаний".
---

# kb-maintain — Guided KB Maintenance Flow

## When to use

User wants the KB brought current but has not specified whether the work is a drift check, a scoped refresh, decision recording, or a sequence of those operations.

This skill is an orchestrator. It does not implement refresh or decision-record logic directly; it delegates to the atomic skills and keeps each write boundary visible to the user.

## Input

- Optional scope path(s), e.g. `src/billing/` or `src/billing/ src/auth/`.
- Optional plan path, e.g. `docs/plans/2026-03-19-1400/plan-billing-rewrite.md`.
- Optional mode words like `check only`, `refresh`, `record decisions`, or `full`.

If the user's intent is ambiguous, ask one short clarification before writing anything.

## Workflow

### 1. Branch on user input

If `.kb/` does not exist, stop and suggest invoking the `kb-build` skill (or `/kb-build`).

Then choose a path:

- **Explicit scope provided** (`/kb-maintain src/billing/` or one or more path arguments) → **fast path**, see step 2a. Skip drift-check.
- **Plan path provided** (`/kb-maintain docs/plans/.../plan-X.md` or `--record <plan>`) → **record path**, see step 2b. Skip drift-check.
- **No arguments** → **discovery path**, see step 2c. Invoke `kb-check-drift` to surface candidates first.

The drift-check is read-only and never modifies `.kb/`. Skipping it on the fast/record paths is safe: the user already specified what to do.

### 2a. Fast path — direct refresh

Invoke the `kb-refresh` skill once with the full list of approved paths. Prefer one call with multiple paths over N sequential calls — see `kb-refresh`'s multi-path input contract.

If the user gave one path, that is one batched refresh of one path. If many, that is one batched refresh of many. Either way: one invocation, one `git diff`, one state advance.

After the refresh returns, surface any decision candidates the refresh reported and ask whether to also record them (step 2b for each approved plan).

### 2b. Record path — decision recording

Invoke the `kb-record-decision` skill with the plan path. The skill writes exactly one file (the decision record) and does not edit summaries — that is the inverted-linkage contract baked into `kb-record-decision`.

After it returns, surface any refresh follow-up it recommended and ask whether to also refresh (step 2a for the recommended paths).

### 2c. Discovery path — drift-first

Invoke the `kb-check-drift` skill with `--write-artifact` so it writes `.kb/.drift-report.json` alongside the human-readable report. `kb-refresh` will reuse the artifact in step 4, skipping a second `git diff` over the same range.

The drift report is read-only and gives the user a maintenance menu. Then go to step 3.

### 3. Propose an explicit maintenance plan (discovery path only)

Turn the drift report into a short ordered plan:

1. Refresh candidates: invoke the `kb-refresh` skill with `<path1> <path2> ...` (batched, one call).
2. Decision candidates: invoke the `kb-record-decision` skill with `<plan-path>`.
3. Any hard flags that should block work until the user resolves them.

Ask the user to approve the plan before invoking any writing skill.

### 4. Run approved refreshes (discovery path only)

Invoke the `kb-refresh` skill once with the full list of approved paths. Do not split into N sequential calls — that re-runs `git diff` and re-advances state once per path. The skill's multi-path input is designed for this.

Rules:

- Preserve the scopes chosen by the user. Do not collapse `src/auth/` and `docs/` into a whole-corpus refresh — that loses the user's choice to skip an unrelated area.
- If a refresh reports decision candidates, append them to the decision queue but do not record them automatically.

### 5. Run approved decision records

For each approved completed plan, invoke the `kb-record-decision` skill with `<plan-path>` as input.

Rules:

- Do not record decisions for incomplete plans.
- `kb-record-decision` does not advance `.kb/.kb-state.json`. If it recommends a follow-up refresh, add it to the queue and ask before running it.

### 6. Final report

Report:

- Path taken (fast / record / discovery).
- Drift candidates reviewed, if applicable.
- Refreshes run and final state SHA, if any refresh advanced it.
- Decision records written.
- Remaining suggested commands, if the user declined some work.

## Discipline

- **No hidden writes.** Every `.kb/` mutation must be attributable to either `kb-refresh` or `kb-record-decision`.
- **No automatic escalation.** A read-only drift check never turns into writes without user approval.
- **Do not merge atomic skills.** This orchestrator exists so `kb-refresh` and `kb-record-decision` can stay simple, auditable, and independently invokable.
- **Batch refresh by default.** When multiple paths need refreshing, send them all in a single `kb-refresh` call — not N calls — to avoid N `git diff`s and N state advances.

## References

- Drift check: invoke the `kb-check-drift` skill (or `/kb-check-drift`).
- Refresh: invoke the `kb-refresh` skill (or `/kb-refresh`).
- Decision recording: invoke the `kb-record-decision` skill (or `/kb-record-decision`).
- Refresh strategy: [docs/refresh-strategy.md](../../docs/refresh-strategy.md)
