---
name: kb-record-decision
description: Use when a completed plan's shipped decisions should be preserved as durable knowledge. Extracts a decision record from a completed plan, writes it to .kb/decisions/, and links it from affected summaries. Triggers on "record the decision", "distill the plan", "extract decisions", "создать decision record", "сохранить решения из плана".
---

# kb-record-decision — Record Shipped Decisions from Completed Plans

## When to use

A plan in `docs/plans/<timestamp>/plan-<slug>.md` (or similar) is complete — the work shipped, the checklist is ticked, the code reflects the decisions made. The user wants the durable choices preserved in the KB without carrying the operational noise of the plan itself.

Manual, on-demand. Never automatic. Never invoked by build.

## Input

- **Plan path** — path to a completed plan file or its containing directory. If missing, ask.

## Output

- One decision record at `.kb/decisions/<YYYY-MM-slug>.md`.
- Updated area summaries that now reference the decision record (user confirms which).
- The source plan is left untouched. Never modify `docs/plans/`.

## Workflow

### 1. Read the plan in full

Read `<plan-path>`. If a sibling `checklist-*.md` exists, read that too. Extract:
- What problem the plan was solving.
- What decision was made.
- What alternatives were considered and rejected.
- Which parts of the codebase / KB the decision affects.

### 2. Confirm the plan is complete

Before recording, verify:
- Checklist items are all ticked (if a checklist exists).
- Git log shows commits implementing the plan have landed.

If neither holds, warn the user. A plan recorded before it's actually done captures intent, not decision. Intent belongs in the plan; decisions belong in `.kb/decisions/` only once they've shipped.

### 3. Draft the decision record

Use `templates/decision.template.md` as shape. Fields:

- **Date** — YYYY-MM (month precision is enough; exact date stays in the plan).
- **Slug** — kebab-case, derived from the plan filename.
- **Decision** — one or two sentences. What was decided.
- **Context** — 2–5 sentences. The problem that forced the choice.
- **Alternatives considered** — list with one-line rationale for each rejection.
- **Consequences** — what changes in code / architecture / process.
- **Affected areas** — list of `.kb/summaries/<area>/<leaf>.md` paths this decision shapes.
- **Source plan** — path to the original plan file.

Target 150–300 words total. If it's longer, you haven't recorded a decision — you've copied the plan.

### 4. Propose target summaries

Based on "Affected areas" in the record, list the summary files that should link to the decision. Ask the user to confirm which should receive the reference. Default to all listed.

### 5. Write the record

Write the decision record to `.kb/decisions/<YYYY-MM-slug>.md`. The filename format is strict: `<YYYY-MM>-<kebab-slug>.md`. This lets `/kb-check-drift` match plans to existing records.

### 6. Update affected summaries

For each confirmed summary, append or update a `## Key decisions` section with a link:

```markdown
## Key decisions

- [2026-03 — fee-calculation rewrite](../../decisions/2026-03-fee-calculation-rewrite.md) — why the pipeline was flattened; rejected alternatives included schema-per-tier.
```

If the section already exists, append the new entry with most-recent-first ordering.

### 7. Check refresh follow-up

This skill never advances `.kb/.kb-state.json`. After updating summaries, check whether the source code or docs affected by the plan are newer than the current refresh watermark (`last_linted_sha`).

- If the plan's affected code paths have not been refreshed, recommend `/kb-refresh <affected-path>`.
- If `/kb-refresh` already covered the affected path, say so.
- Do not run `/kb-refresh` automatically unless the user explicitly asked for the whole maintenance flow.

### 8. Report

Tell the user:
- Record written at `.kb/decisions/<path>`.
- Summaries updated (list paths).
- Refresh follow-up needed, if any, with `/kb-refresh <affected-path>`.
- Plan file left untouched.

## Discipline

- **Record shipped decisions, not intentions.** Code must reflect the decision before the record is written.
- **One decision record per decision.** If the plan covered two unrelated choices, write two records. The KB separates them even when the plan doesn't.
- **Records stand alone.** Do not write "see plan X for details". Plans may be archived or deleted; the record must remain complete.
- **Never modify the plan.** Plans are historical artifacts. The record is a distilled copy, not a replacement.
- **No top-level `decisions` area in `_root.md`.** Decisions are reached via the summaries they affect, not as a separate navigation dimension.

## Failure modes

- **Plan covers no real decision** — it was pure execution, no choice points. Tell the user; don't write a record. Not every plan deserves distillation.
- **Decision is too small** — "we renamed function X" is not a decision record.
- **Decision was reversed later** — if a newer decision supersedes this one, add a "Superseded by" line in the older record. If distilling an already-superseded plan, stop and confirm with the user.

## References

- Decision template: [templates/decision.template.md](../../templates/decision.template.md)
- Pattern rationale: [docs/concept.md](../../docs/concept.md)
- Drift surfacing: [skills/kb-check-drift/SKILL.md](../kb-check-drift/SKILL.md)
