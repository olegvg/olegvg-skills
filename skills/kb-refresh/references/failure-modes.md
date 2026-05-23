# Failure Modes for kb-refresh

When to stop, ask the user, or recover.

## `.kb/.kb-state.json` missing

Never ran `kb-build`, or the state file was deleted.

**Action.** Stop. Suggest invoking `kb-build` (or `/kb-build`). Do not auto-build — the corpus root and scope are explicit choices the user must make.

## `last_linted_sha == "no-git"`

Corpus is not in git. `kb-refresh` and `kb-check-drift` both require git history.

**Action.** Tell the user. Suggest either `git init` + an initial commit, then re-running `kb-build`, or accepting that the KB is frozen (use `kb-build` to rewrite it from scratch when needed).

## `last_linted_sha` not reachable from HEAD

Force-push, history rewrite, or a branch that diverged. `git diff <base>..HEAD` returns an empty or nonsensical diff.

**Signal.**

```bash
git -C <corpus-root> merge-base --is-ancestor <base_sha> HEAD
# Returns non-zero → not reachable.
```

**Action.** Ask the user how to recover. Two safe options:

1. **Full re-read of scope.** Treat the full history of `<path>` as diff scope: read everything in scope as if writing summaries from scratch. Slow, but correct.
2. **Reset watermark explicitly.** User specifies a known-good prior SHA via `--base-sha <sha>`, accepting that anything between then and the broken watermark may not have been refreshed.

Do not silently fall back. Confirm before proceeding.

## Merge conflicts in the diff scope

The user has unmerged paths in their working tree. The diff is ambiguous.

**Signal.**

```bash
git -C <corpus-root> diff --name-only --diff-filter=U
# Returns one or more files.
```

**Action.** Stop. Ask the user to resolve the merge first. A refresh that runs on an unresolved tree produces summaries that match neither side of the conflict.

## Refresh scope exceeds budget (hard gate)

The diff is large enough that the main agent cannot patch all affected summaries inline without running out of context. This is the failure mode that ends in "hit usage limit" — the agent reads source files, opens summaries, makes Edits, and never finishes because each step adds to the running context.

The `## Scope budget` table in `SKILL.md` defines the thresholds. Step 4.5 of the workflow checks them and routes accordingly. This failure mode is the **hard-threshold** branch of that routing.

**Signal.** Any of these after step 3 (diff) and step 4 (grep):

```bash
# changed source files (excluding .kb/ itself)
git -C <corpus-root> diff --name-only <base>..HEAD -- <path> | grep -v '^\.kb/' | wc -l   # >= 25

# total diff size
git -C <corpus-root> diff --shortstat <base>..HEAD -- <path>                              # >= 3000 lines

# affected summaries
grep -rl ... .kb/summaries/ | wc -l                                                        # >= 15

# distinct KB areas touched
grep -rl ... .kb/summaries/ | awk -F/ '{print $3}' | sort -u | wc -l                       # >= 5
```

**Action.** STOP. Do **not** fall back to subagent dispatch — that helps the soft band, not this one. Report to the user:

- The counts that tripped.
- The list of touched KB areas.
- Suggested narrower invocations, one per area or sub-area, e.g.:
  `/kb-refresh src/auth/`, `/kb-refresh src/billing/`, `/kb-refresh src/search/`.
- If structural change is large in a specific area (new top-level concepts, renamed modules, new subdomains), recommend `kb-build` for that area instead — refresh is for patching, not rewriting.

Do not silently split scope on the user's behalf and do not advance state. The path arg is the user's lever; this skill enforces the budget but does not redraw the scope.

## Bare invocation with no scope

User ran `/kb-refresh` with no path argument and the harness is in a non-interactive mode (auto, agentic loop), so the agent cannot ask interactively.

**Antipattern.** Inferring scope from `git status`, picking "the whole corpus", or running a diff from the watermark to HEAD over everything. All three end in the scope-budget failure above, except worse — because the agent has already spent context discovering the scope before it knows the scope is too big.

**Action.** Route through step 0 of the workflow:

1. Invoke `kb-check-drift` with `--write-artifact`. This is read-only.
2. Surface the drift report's grouped refresh candidates to the user as a structured proposal (one-line per candidate path, with the reason).
3. Wait for an explicit path list from the user. Even in auto mode, surface the proposal and ask — auto mode means "don't ask trivial clarifications", not "make architecturally expensive choices alone".
4. Once the user replies, continue with step 1 of the workflow using the approved path list.

If the harness genuinely cannot surface a question, **stop and report** — write the drift report's recommended commands to stdout and exit. Do not pick a scope yourself.

## Refresh would touch a summary outside the scope

A summary references a changed file that lives inside the scoped path, but the summary itself covers more than that path. Refreshing it may stray outside scope.

**Action.** Refresh the summary. The contract is "scoped by which source files changed," not "scoped by which summary paths." A summary that spans multiple areas is the user's choice; if you encounter this often, the area split is wrong (a separate refresh-strategy concern).

## Drift artifact stale

`.kb/.drift-report.json` exists, but its `head_sha` does not match the current HEAD.

**Signal.**

```bash
[[ "$(jq -r .head_sha .kb/.drift-report.json)" != "$(git rev-parse HEAD)" ]]
```

**Action.** Ignore the artifact; fall back to the normal `git diff` flow. Do not warn the user — drift artifacts are ephemeral and may be stale by design. (Optionally: delete the stale file so the next drift check rewrites it cleanly.)

## State write failed

Disk full, permission error, or the `.kb/` directory was deleted mid-refresh.

**Action.** Do **not** retry blindly. The refresh has done some writes (summaries, indexes) but the state advance failed. Two options:

1. Re-run the refresh from scratch — safe because refresh is idempotent against the same diff.
2. Manually advance state if the user is confident the refresh completed: write `.kb/.kb-state.json` with the head SHA and the current ISO timestamp.

The skill must not silently leave `last_linted_sha` mid-update. If state cannot be written, fail loudly.
