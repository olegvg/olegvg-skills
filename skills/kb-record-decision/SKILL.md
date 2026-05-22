---
name: kb-record-decision
description: Use when a completed plan's shipped decisions should be preserved as durable knowledge. Extracts a decision record from a completed plan and writes it to .kb/decisions/. Triggers on "record the decision", "distill the plan", "extract decisions", "создать decision record", "сохранить решения из плана".
---

# kb-record-decision — Record Shipped Decisions from Completed Plans

## When to use

A plan in `docs/plans/<timestamp>/plan-<slug>.md` (or similar) is complete — the work shipped, the checklist is ticked, the code reflects the decisions made. The user wants the durable choices preserved in the KB without carrying the operational noise of the plan itself.

Manual, on-demand. Never automatic. Never invoked by build.

## Input

- **Plan path** — path to a completed plan file or its containing directory. If missing, ask.

## Output

- **One** decision record at `.kb/decisions/<YYYY-MM-slug>.md`. That is the only file this skill writes.
- The source plan is left untouched. Never modify `docs/plans/`.
- The summaries listed in the record's `## Affected areas` block are **not edited** — they remain the agent's view of the present, the decision-record carries the link to them, not the other way around. `kb-query` reaches a decision via that backreference (`grep -l "<summary-path>" .kb/decisions/`).

## Workflow

### 1. Read the plan

Read `<plan-path>`. If a sibling `checklist-*.md` exists, read that too. Extract:

- What problem the plan was solving.
- What decision was made.
- What alternatives were considered and rejected.
- Which parts of the codebase / KB the decision affects.

For plans larger than ~1500 lines, do not read the whole file — see [references/large-plan-strategy.md](references/large-plan-strategy.md).

### 2. Confirm the plan is complete

Before recording, verify:

- Checklist items are all ticked (if a checklist exists): `grep -c '^- \[ \]' <checklist-path>` returns 0.
- Git log shows commits implementing the plan have landed.

If neither holds, stop. See [references/failure-modes.md](references/failure-modes.md) for the "plan not yet complete" path.

### 3. Draft the decision record

Use the shape and field rules in [references/decision-template.md](references/decision-template.md). Required fields:

- **Date** — `YYYY-MM` only.
- **Slug** — `kebab-case`, derived from the plan filename.
- **Decision** — one or two sentences.
- **Context** — 2–5 sentences.
- **Alternatives considered** — one line per rejection.
- **Consequences** — what changes.
- **Affected areas** — `.kb/summaries/<area>/<leaf>.md` paths this decision shapes. This list is the **only** linkage between the record and the summaries it affects.
- **Source plan** — path to the original plan.

Target **150–300 words total**. Longer means you copied the plan instead of distilling.

### 4. Confirm `Affected areas` with the user

Show the user the proposed `Affected areas` list and ask for confirmation. This list determines discoverability — a missing entry hides the decision from agents querying those summaries.

If a relevant summary does not yet exist (e.g. the plan added a new area that has not been refreshed into `.kb/`), include the *future* path in the list and note it as a refresh follow-up in step 7. Do not invent placeholder summary files from inside this skill.

### 5. Write the record

Write to `.kb/decisions/<YYYY-MM>-<slug>.md`. The filename format is strict — drift-check matches plans to records by slug.

That is the **only** write this skill performs.

### 6. Verify discoverability

The `Affected areas` block is the backreference. Verify it works by running:

```bash
grep -l "<one-of-the-affected-summary-paths>" .kb/decisions/
```

The just-written record should appear. If it does not, the paths in `Affected areas` are wrong — fix them and rewrite. **Never** edit the summaries themselves to add a forward link; that is the inverted contract this skill exists to enforce.

If your repo wants a materialized index of "summary → decisions that mention it", generate it from outside the skill via a script that walks `.kb/decisions/*.md` and writes a derived file. Do not bake that into this skill.

### 7. Check refresh follow-up

This skill never advances `.kb/.kb-state.json`. After writing the record, check whether the source code or docs affected by the plan are newer than the current refresh watermark (`last_linted_sha`).

- If the plan's affected paths have not been refreshed, recommend `/kb-refresh <affected-path>`.
- If the summaries named in `Affected areas` do not yet exist, recommend `/kb-refresh <path>` to create them.
- If `/kb-refresh` already covered the affected path, say so.
- Do not run `/kb-refresh` automatically unless the user explicitly asked for the whole maintenance flow.

### 8. Report

Tell the user:

- Record written at `.kb/decisions/<path>`.
- Affected summaries (the list from the record).
- Refresh follow-up needed, if any, with `/kb-refresh <affected-path>`.
- Plan file left untouched.
- Summaries left untouched — the link lives in the record.

## Discipline

- **Record shipped decisions, not intentions.** Code must reflect the decision before the record is written.
- **One decision record per decision.** If the plan covered two unrelated choices, write two records.
- **Records stand alone.** Do not write "see plan X for details". Plans may be archived or deleted; the record must remain complete.
- **Never modify the plan.** Plans are historical artifacts. The record is a distilled copy, not a replacement.
- **Never modify summaries.** The `Affected areas` list inside the record is the only backreference. Summaries describe the present; decisions describe how the present was chosen. Mixing forward and back links in both directions creates churn that this skill exists to avoid.
- **No top-level `decisions` area in `_root.md`.** Decisions are reached via the summaries they affect, not as a separate navigation dimension.

## Failure modes

See [references/failure-modes.md](references/failure-modes.md): plan covers no real decision, decision too small, decision reversed, plan not yet complete, missing affected areas, conflicting plans, in-progress recording requests.

## References

- Decision template and field rules: [references/decision-template.md](references/decision-template.md)
- Reading large plans: [references/large-plan-strategy.md](references/large-plan-strategy.md)
- Failure modes: [references/failure-modes.md](references/failure-modes.md)
- Pattern rationale: [docs/concept.md](../../docs/concept.md) (in this repo) or `templates/README.md` (in the user corpus, when bundled).
- Drift surfacing: invoke the `kb-check-drift` skill (or `/kb-check-drift`).
