# Decision Record Template

Use this shape when drafting a record. Keep the whole record between **150–300 words**. Longer means it was not distilled — it was copied. A record that needs the source plan to be intelligible has failed its purpose; the plan may be archived or deleted and the record must still stand alone.

## Shape

```markdown
# <YYYY-MM> — <decision slug>

**Decision.** One or two sentences. What was decided.

## Context

2–5 sentences describing the problem that made this decision necessary.
Constraints, requirements, failure modes — why a choice was forced.

## Alternatives considered

- **<alt-1>** — one line on why rejected.
- **<alt-2>** — one line on why rejected.
- **<alt-3>** — one line on why rejected.

## Consequences

What changes as a result: code shape, process, follow-on obligations,
trade-offs accepted.

## Affected areas

- `.kb/summaries/<area-a>/<leaf>.md`
- `.kb/summaries/<area-b>/<leaf>.md`

## Source plan

`docs/plans/<timestamp>/plan-<slug>.md`
```

## Field rules

- **Date.** `YYYY-MM` only. Exact day stays in the plan; month precision is enough for a durable record.
- **Slug.** `kebab-case`, derived from the plan filename. The filename of the record is `<YYYY-MM>-<slug>.md` — strict, because drift-check matches plans to records by slug.
- **Decision.** One or two sentences. If you need a paragraph, you are not done distilling.
- **Context.** Why the choice was forced. Constraints and failure modes, not the history of how you got here.
- **Alternatives considered.** Each rejection is one line. If a rejection needs three paragraphs, write a separate decision record for the alternative path that was rejected — and link both.
- **Consequences.** The shape change in code, process, obligations.
- **Affected areas.** Paths under `.kb/summaries/`. This is the **only** backreference between a decision and the summaries it shapes; the summaries themselves do not list decisions. The agent finds decisions by grepping this list (`grep -l "summaries/auth/session.md" .kb/decisions/`).
- **Source plan.** Path to the original. The record stands on its own; the plan path is provided for archaeologists.

## A worked example

```markdown
# 2026-03 — fee-calculation rewrite

**Decision.** Flatten the per-tier fee pipeline into a single dispatch table keyed by
`(plan_id, currency, region)`; remove the `FeeCalculator` class hierarchy.

## Context

Pricing changes required edits across four `FeeCalculator` subclasses and three
`FeeStrategy` mixins. Three production incidents in Q1 traced to inconsistent
overrides between the hierarchy layers. Performance was acceptable; correctness
was not.

## Alternatives considered

- **Keep the hierarchy, add a contract test per subclass** — would only have surfaced
  divergence after a rollout; the root cause was implicit override order, not missing tests.
- **Schema-per-tier (separate tables per plan)** — multiplied DDL churn for every pricing
  experiment; rejected because pricing changes weekly.
- **Move to an external pricing service** — too much surface for a 2-week rewrite;
  revisit when international tax compliance lands.

## Consequences

- One `fee_dispatch` table; one `lookup_fee()` function; no inheritance.
- New currency or region is a row insert, not a class definition.
- Loses ability to share helper methods across "kinds" of fees — duplication
  is now explicit (and observable) rather than implicit (and dangerous).
- Migration deferred for legacy customers on grandfathered plans; tracked separately.

## Affected areas

- `.kb/summaries/billing/fee-calculation.md`
- `.kb/summaries/billing/pricing-experiments.md`
- `.kb/summaries/data-model/billing-tables.md`

## Source plan

`docs/plans/2026-03-19-1400/plan-billing-rewrite.md`
```

## Pre-flight checks

Before writing the record, confirm:

- Total length is 150–300 words. If you went long, the alternatives list usually has stowaways — split into separate records.
- The "Alternatives considered" list does not silently reintroduce the plan's discussion. Each rejection is one short line; the *why* is enough, the history is noise.
- The "Affected areas" list points at actual files in `.kb/summaries/` (not future paths). If a summary does not yet exist for an area the decision affects, that is a refresh follow-up — note it in the final report, but do not invent the summary path.
