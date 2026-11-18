---
name: kb-build
description: Use when building a fresh three-layer knowledge base for a corpus. Walks the corpus, groups files by semantic domain, writes summaries and indexes into .kb/. Triggers on "build the knowledge base", "map this corpus", "ingest the corpus", "создать kb", "сгенерировать базу знаний".
---

# kb-build — Build a Three-Layer Knowledge Base

## When to use

User points you at a corpus (codebase, notes archive, docs folder) and wants a fresh `.kb/` built from scratch. One-shot operation.

If `.kb/` already exists at the target path, STOP. Ask the user whether to overwrite, and get explicit confirmation before proceeding.

## Input

- **Corpus root path** — argument from the user. If missing, ask for it before starting. Default is not the current directory unless the user confirms.
- **`--include <path>`** (optional, repeatable) — override a default exclusion. See [references/default-exclusions.md](references/default-exclusions.md).

## Output (created inside the corpus root)

```
.kb/
├── indexes/_root.md
├── indexes/<area>.md       (one per semantic domain)
├── summaries/<area>/overview.md
├── summaries/<area>/<leaf>.md
├── decisions/              (empty directory — populated only by kb-record-decision)
└── .kb-state.json
```

## Default exclusions

Build never ingests dated planning artifacts, vendored directories, build outputs, or timestamped scratch directories. Full list and rationale: [references/default-exclusions.md](references/default-exclusions.md). Override individual paths with `--include`.

## Workflow

Build runs in **three passes**. The structure is deliberate: it keeps the main agent's context bounded regardless of corpus size, and it parallelizes the expensive pass. Do NOT collapse it into a single pass even on small corpora — the workflow is the teaching.

### Pass 1 — Survey and group (main agent, light context)

Walk the corpus at a high level. Do NOT read full file contents in this pass.

- `ls <corpus-root>` for the top-level layout.
- Read README if present.
- For each directory worth sampling, read only **file headers**: first 30–50 lines, docstrings, imports, exported names.
- Cluster files into semantic domains. Produce a draft of `_root.md` in memory — list of areas + which files belong to each.

Context budget for Pass 1: roughly 5–10% of the corpus. If you catch yourself opening full file bodies in Pass 1, stop — that's Pass 2's job.

#### Grouping (the critical step)

Group files by **what a user would ask about them**, not by where they sit in the filesystem. Good: `auth`, `billing`, `search-indexing`. Bad: `src`, `tests`, `utils`, `scripts`.

A domain is a set of files someone would want to understand together when working on a task. Name each domain with a short kebab-case slug. 4–10 domains is typical.

Detailed rules, examples, and "how to tell when grouping is wrong" live in [references/semantic-grouping.md](references/semantic-grouping.md).

### Pass 2 — Deep build per domain (dispatch subagents)

For each domain identified in Pass 1, dispatch a subagent via the Task tool. The subagent starts with a fresh context and sees only its slice of the corpus.

Use the prompt shape and contract in [references/subagent-prompt.md](references/subagent-prompt.md). Key contract points:

- Subagent reads its file list fully and writes summaries under `.kb/summaries/<area-slug>/`.
- Subagent does **not** write to `.kb/indexes/` — that is Pass 3's job.
- Subagent returns a ≤200-word brief: area name, leaves created, one-line description of each leaf.

Dispatch subagents in parallel where the host environment supports it. You (main agent) do NOT read corpus files during Pass 2. You hold only the briefs returned by subagents. This is the key context-window guarantee of the pattern.

### Pass 3 — Index assembly (main agent, holds only briefs)

Based on the briefs returned from Pass 2:

#### 3a. Write area indexes (Layer 3)

For each domain, create `.kb/indexes/<area>.md` following [templates/index.template.md](templates/index.template.md).

- Maximum 300 tokens. Measure. If you overshoot, split the area or drop signposts.
- Sections: what the area covers, when to enter it, list of leaves with one-line descriptions, optional "see also".

#### 3b. Write `_root.md`

Create `.kb/indexes/_root.md` following [templates/_root.template.md](templates/_root.template.md).

- Maximum 300 tokens.
- One line per area: pointer + one-sentence description.
- Include navigation rules inline so an agent reading it knows the conventions.

#### 3c. Create empty `decisions/` directory

```bash
mkdir -p <corpus-root>/.kb/decisions
```

This is empty on fresh build. It is populated by `kb-record-decision` when the user asks to extract a decision record from a completed plan. Never populate it during build — build looks at current state, not history.

#### 3d. Write `.kb-state.json`

Capture the current corpus git SHA and an ISO-8601 UTC timestamp:

```bash
git -C <corpus-root> rev-parse HEAD
date -u +"%Y-%m-%dT%H:%M:%SZ"
```

Write to `.kb/.kb-state.json` with `schema_version: 1`. Shape: [templates/.kb-state.template.json](templates/.kb-state.template.json).

If the corpus is not a git repo, set `last_linted_sha` to the string `"no-git"` and note this to the user — `kb-refresh` and `kb-check-drift` will not work until the corpus is in git.

### Fallback when subagents are unavailable

If the host environment cannot dispatch subagents, run build iteratively across separate sessions, one per domain: invoke `kb-build <domain-path>` once per area. Each session does a narrow Pass 2 for one domain and writes its own area index. A final session runs Pass 3 to write `_root.md` and `.kb-state.json`. Slower and less clean than the subagent path, but works.

## Discipline

- **Index token budget is 300 tokens, not "about 300".** Enforce on write. If you overshoot, split or trim.
- **Indexes contain signposts, not content.** No prose explanations in index files. If you need prose, it belongs in a summary.
- **Semantic grouping beats structural grouping.** When in doubt, ask: "would a user ask about these files together?" — not "are these files in the same folder?".
- **Three passes, never collapsed.** Pass 1 reads headers; Pass 2 dispatches subagents that read deeply; Pass 3 reads only briefs. The structure is the context-window guarantee.
- **Subagents never write indexes.** Indexes are global; only Pass 3 (main agent) sees the full brief set.

## Failure modes

See [references/failure-modes.md](references/failure-modes.md): building by directory, overlong indexes, empty summaries, reading bodies in Pass 1 or Pass 3, sequential Pass 2, auto-compact triggered, subagents writing indexes, state written before content.

## References

- Default exclusions: [references/default-exclusions.md](references/default-exclusions.md)
- Semantic grouping rules: [references/semantic-grouping.md](references/semantic-grouping.md)
- Subagent prompt and contract: [references/subagent-prompt.md](references/subagent-prompt.md)
- Failure modes: [references/failure-modes.md](references/failure-modes.md)
- Pattern rationale: [docs/concept.md](https://github.com/olegvg/olegvg-skills/blob/master/docs/concept.md)
- Navigation rules: [docs/navigation-rules.md](https://github.com/olegvg/olegvg-skills/blob/master/docs/navigation-rules.md)
- Templates: [templates/](templates/)
