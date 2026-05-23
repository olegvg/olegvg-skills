# Subagent Dispatch for Multi-Area Refresh

When `kb-refresh` step 4.5 lands in the **between soft and hard threshold** band, the main agent dispatches one subagent per affected KB area instead of patching summaries inline. The pattern mirrors `kb-build` Pass 2, but the contract differs because refresh **patches existing summaries** rather than building them from scratch.

This is the difference between a refresh that fits in one context window and one that does not.

## What an "area" means here

An area is a single top-level directory under `.kb/summaries/`. Example areas in a typical Python service KB: `pipeline-orchestration`, `data-providers`, `semantic-pipeline`, `strategy-reports`, `agent-skills`, `repo-conventions`.

One subagent owns exactly one area. If the diff touches 5 areas, dispatch 5 subagents (in parallel where the host supports it).

## Inputs the main agent prepares per subagent

Before dispatch, the main agent produces these per area:

1. **Area name** — the directory slug under `.kb/summaries/`.
2. **Changed source files relevant to this area** — the subset of step 3's diff that lives in this area's scope. This is the file list the subagent will read diff hunks for. Keep it tight; do not pass the whole step-3 diff list.
3. **Summaries in this area that need review** — the subset of step 4's affected summaries that fall under `.kb/summaries/<area>/`.
4. **Base SHA** — the watermark from step 1.
5. **Corpus root** — absolute path so the subagent can run `git -C` cleanly.

If two areas share a changed source file, both subagents get that file in their input list. Cross-area linkage is the index agent's concern, not the area subagent's.

## The prompt shape

Adapt wording; **preserve the contract** (what the subagent reads, what it writes, what it returns).

```
Area: <area-slug>
Base SHA: <base_sha>
Corpus root: <abs/path/to/corpus>

Changed source files in this area:
  - <path/to/file1>
  - <path/to/file2>
  - ...

Summaries to review:
  - .kb/summaries/<area>/<leaf1>.md
  - .kb/summaries/<area>/<leaf2>.md
  - ...

Your task:
  1. For each changed source file, run:
        git -C <corpus-root> diff <base_sha>..HEAD -- <source_file>
     and read the diff hunks. Open the full source file ONLY when you
     need to verify a specific line number for a summary's
     `## References` block, or when the diff context is too thin to
     understand what changed.
  2. For each summary in your review list, patch where content has
     shifted. Prefer surgical Edit calls. Keep one-topic-per-file
     discipline.
  3. If a new topic appears that does not fit any existing leaf
     (e.g. a new module, a new subsystem), write a new summary file
     at .kb/summaries/<area>/<new-leaf>.md. Follow
     templates/summary.template.md.
  4. If an existing summary's scope has grown past one topic, split
     it into two leaves and note the split in your brief so the main
     agent can update the area index.
  5. Return a brief, max 200 words:
       - summaries patched (with paths)
       - summaries added (with paths)
       - summaries split (old path → new paths)
       - suggested index changes (one line each — main agent applies)
       - any decision-record candidates noticed (file path to plan
         that appears completed)

Rules:
  - Do NOT write to .kb/indexes/. The main agent updates indexes in
    step 6 from your brief and the briefs of other area subagents.
  - Do NOT update .kb/.kb-state.json. The main agent advances state
    in step 8 after all areas return.
  - Do NOT touch summaries outside .kb/summaries/<area>/.
  - Do NOT read files outside your assigned changed-source list. If
    you need cross-area context, note it in the brief and let the
    main agent cross-link.
  - Read diffs before full files. Pre-opening every changed source
    file blows the subagent's own context window.
```

## Why this shape

- **"Read diffs first"** — the failure mode kb-refresh is defending against is "main agent opens every changed file in full to ground updates." Pushing that work into subagents only helps if the subagents also avoid it. The diff hunk is the unit of refresh.
- **"Do NOT write to indexes"** — indexes are a global concern. Each subagent sees only its area; index writes need the full brief set. Same rule as `kb-build` Pass 2.
- **"Do NOT update state"** — the main agent decides whether to advance `.kb-state.json` after collecting all briefs, and skips it under `--no-advance-state`. A subagent that wrote state would race other subagents and break atomicity.
- **"Max 200 words"** — the brief is what flows back into the main agent's context. With 5 area subagents, that is 1000 words of brief — easily under one context window. With unbounded briefs, the main agent's index step (6) hits the same wall the inline path would.

## What the main agent does with the briefs

After all area subagents return:

1. **Step 6 (indexes)** — for each area that reported summary additions / removals / splits in its brief, update the area index. If a new area emerged or one disappeared, update `_root.md`. The main agent reads only the briefs plus the existing index files — never the area summaries themselves at this stage.
2. **Step 7 (decision candidates)** — aggregate decision-record candidates from all briefs; surface as follow-up `kb-record-decision <plan>` recommendations.
3. **Step 8 (state)** — single state advance (or single skip under `--no-advance-state`).

This is the context-window guarantee of multi-area refresh: the main agent holds N briefs + N indexes + 1 root index. Not N areas of summaries × M source files.

## Parallelism

Dispatch subagents in parallel where the host environment supports it. Each subagent is independent — its inputs (file list, summary list) and outputs (patched summaries + brief) do not depend on other subagents. Parallelism is the difference between a refresh that takes minutes and one that takes an hour.

If the environment does not support subagents, fall back to running `kb-refresh` once per area in separate sessions, each with an explicit area-scoped path. Slower but produces the same artifacts and keeps each session's context bounded.

## When NOT to dispatch

Step 4.5 says to dispatch between soft and hard thresholds. Below the soft threshold, inline patching (step 5a) is cheaper than the dispatch overhead — subagent setup has its own cost. Above the hard threshold, even subagents will not save you, because the main agent's coordination step (briefs + indexes for many areas) hits the wall. Stop and ask the user to narrow scope instead.
