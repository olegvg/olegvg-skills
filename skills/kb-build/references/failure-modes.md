# Common Failure Modes in kb-build

When the three-pass workflow goes wrong, it tends to go wrong in the same handful of ways.

## Building by directory

The build produces areas named `src`, `tests`, `utils`, `scripts`. The indexes mirror `ls`. Navigation provides no advantage over the filesystem.

**Cause.** Pass 1 grouped by directory structure instead of by task surface.

**Fix.** Re-group. Ask: "what would a user ask about these files together?" See [references/semantic-grouping.md](semantic-grouping.md). It is usually faster to redo the build with better grouping than to refactor the produced KB.

## Overlong indexes

An `.kb/indexes/<area>.md` exceeds the 300-token budget after Pass 3.

**Cause.** The area covers too many leaves, or each leaf description ran long.

**Fix.** Two options. (a) Split the area into two — the most common fix. (b) Compress leaf one-liners. **Do not** raise the budget. The 300-token cap is non-negotiable; the budget is what makes navigation cheap.

## Empty summaries

A leaf summary has nothing to say beyond a pointer (e.g., "see X for details"). The file is content-free.

**Cause.** What you thought was a separate topic was actually a section of another topic.

**Fix.** Delete the empty leaf, fold its pointer into the natural parent summary, and update the area index.

## Reading full file bodies in Pass 1 or Pass 3

The main agent's context grows past the corpus survey budget. Inference slows; quality drops.

**Cause.** Discipline failure. Pass 1 reads headers only; Pass 3 reads only briefs. All deep reading happens inside Pass 2 subagents.

**Fix.** Restart the affected pass. If Pass 1 already strayed, abandon the current group draft and re-run Pass 1 fresh on headers only. The cost of restarting is much smaller than the cost of finishing on a polluted context.

## Running Pass 2 sequentially on a large corpus

The build runs for hours when it should run for minutes.

**Cause.** Subagent dispatch was sequential when the environment supports parallelism.

**Fix.** Re-dispatch in parallel. Each subagent is independent — the host environment is the only constraint.

## Using auto-compact instead of three passes

Mid-build, the main agent runs into context limits and auto-compaction kicks in. Quality after compaction is poor — the agent loses track of which domains it has covered.

**Cause.** The three-pass structure was collapsed (e.g., "let me just read everything sequentially and write the summaries as I go").

**Fix.** The three passes exist precisely so compaction is never needed. Restart with discipline: Pass 1 headers, Pass 2 subagent fan-out, Pass 3 briefs-only. Do not "try to be efficient" by skipping passes — the structure is the efficiency.

## Subagents writing into `.kb/indexes/`

Two subagents both decided to write `_root.md` (or an area index). The files conflict on commit, or — worse — one silently overwrites the other.

**Cause.** Subagent prompt did not forbid index writes, or the subagent ignored the instruction.

**Fix.** Re-issue Pass 2 with the explicit "Do NOT write to `.kb/indexes/`" instruction in the prompt. Pass 3 (main agent) is the *only* place indexes get written. See [references/subagent-prompt.md](subagent-prompt.md).

## State written before content

`.kb/.kb-state.json` exists, but `.kb/summaries/` is empty or partial.

**Cause.** State write happened before the build finished (Pass 3 wrote state before all subagents returned).

**Fix.** Delete `.kb/.kb-state.json` and re-run Pass 3. The state file is the last thing written, so its presence is the signal that the build completed.
