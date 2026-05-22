# Failure Modes for kb-record-decision

When to stop the skill and tell the user, rather than push through to a record.

## Plan covers no real decision

The plan was pure execution — pre-agreed scope, no choice points, no rejected alternatives discussed. Common shape: a refactor plan with a single "do X" goal and a checklist.

**Signal.** The "Scope And Decisions" (or equivalent) section is short and reads as "we will do X." No comparison of alternatives, no constraints that forced a choice.

**Action.** Tell the user: "This plan does not contain a decision worth distilling — it was execution. No record will be written." Not every plan deserves a record.

## Decision is too small

"We renamed function X" or "We bumped a dependency version" is not a decision record. A record's *Affected areas* list should plausibly contain at least one summary; a rename does not shape a summary.

**Signal.** You can compress the entire decision into the title — there is no real *Context* or *Consequences* to write.

**Action.** Tell the user. Suggest a git commit message or an inline comment in the affected code as the better home. No record.

## Decision was reversed later

A newer decision supersedes this one. Recording the old one without acknowledgment misleads future readers.

**Signal.** `grep -l "<slug-or-topic>" .kb/decisions/` shows a newer record that overrides this one. Or the user mentions "we walked this back."

**Action.** Two options, ask the user which:

1. Add a `> Superseded by [<new-record>](<path>).` line at the top of the older record (write it anyway, with the supersedure note).
2. Skip the record entirely. Mention the newer record in the *Source plan*'s checklist comments if useful.

If distilling a plan that the user already knows was reversed: confirm intent before writing.

## Plan not yet complete

Checklist has unticked items, or git log shows commits implementing it have not landed yet.

**Signal.** `grep -c '^- \[ \]' <checklist-path>` returns a nonzero count.

**Action.** Stop. Tell the user: "This plan is N% complete (X of Y checklist items unticked). A record now captures intent, not decision. Re-run after the work ships." A record written before completion drifts away from reality and silently becomes wrong.

## Affected areas don't exist

The decision shapes a part of the corpus that has no summary yet — the relevant `.kb/summaries/<area>/<leaf>.md` is missing.

**Signal.** The plan obviously touches a new area, but `_root.md` has no such area.

**Action.** Write the record with the *correct future* paths in `Affected areas`. Note this in the final report and recommend `/kb-refresh <affected-path>` — a refresh that creates the missing summaries is now a follow-up. Do not invent placeholder summaries from inside this skill.

## Conflicting plans

Two plans landed in the same area within days of each other and the user wants both recorded.

**Signal.** Two `docs/plans/<timestamp>/...` directories with overlapping scope.

**Action.** Write two separate records. Decisions are atomic — bundling them under one record hides the fact that two choices were made. The records may cross-reference each other in *Consequences* if one constrained the other.

## User asks to record an in-progress plan "to lock in the decision"

Tempting, especially if the user is confident about the choice. But intent is not decision — the code has not yet validated the choice.

**Signal.** User says "we're going to do X, write the record now."

**Action.** Refuse politely and explain: "Records capture shipped decisions, not intentions. The plan itself already captures intent. We'll record once the code lands." If the user insists after explanation, write the record but add `> Status: provisional — code not yet shipped` at the top, and recommend re-validating when the work merges.
