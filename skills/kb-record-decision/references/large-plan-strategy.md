# Reading Large Plans

The skill says "Read the plan in full." For plans larger than ~1500 lines, that is not literal: a complete read blows context for no benefit, since 80% of a long plan is per-task execution detail that does not belong in a decision record.

## When to apply

- Plan exceeds ~1500 lines, or
- Plan has more than 6 top-level sections, or
- Sibling checklist has more than 30 items.

If the plan is smaller, read it whole. The strategy below is overhead you do not need.

## Procedure

1. **Read the outline.** Run:

   ```bash
   grep -nE '^##+ ' <plan-path>
   ```

   This is a cheap headings dump. You learn the plan's table of contents in ~30 lines instead of 2000+.

2. **Read the decision-bearing sections.** From the outline, identify sections that hold *what was decided* and *why*. Common names:

   - `## Goal`, `## Scope And Decisions`, `## Architecture`, `## Constraints`
   - `## Out of scope`, `## What stays unchanged`
   - `## Completion Criteria`, `## Verification`

   Read these in full. They are the substance of the decision record.

3. **Read the checklist.** Sibling `checklist-*.md` is always small enough to read whole. It confirms completion (all items ticked) and reveals which sections shipped vs. were trimmed.

4. **Skim, do not read, the per-task implementation steps.** Sections named `## Task N`, `## Phase N`, `## Step <id>` describe execution, not decisions. Their content is the *how*, not the *what* or *why* — irrelevant to the record.

   If a particular task section is unusually long or labeled "decisions", read that one. Otherwise skip.

5. **Sample at most two implementation sections** if you want to sanity-check that the decisions actually shipped. Grep for the decision keywords in the source code; do not read the whole plan to verify.

## Verification before writing the record

After this targeted read you should be able to answer, without re-reading:

- What problem forced the decision?
- What was decided?
- What was considered and rejected? (Each rejection in one line.)
- What summaries (under `.kb/summaries/`) does this decision shape?

If any of these is unclear, you missed a decision-bearing section. Return to the outline (step 1) and pull one more section, not the whole plan.

## Why this is not "skipping the plan"

A plan is a journal of execution. A record is durable knowledge. Reading the plan in full reads the journal — most of which is irrelevant to what someone will need to know six months from now. The strategy above reads only the parts of the journal that carry durable knowledge. The skill's full-read instruction is the right default for small plans; this file is its escape hatch for large ones.
