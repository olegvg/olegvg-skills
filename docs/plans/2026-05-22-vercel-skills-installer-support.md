# vercel-labs/skills Installer Support — Implementation Plan (executed 2026-05-22)

> **Status:** Executed. This document records what was done and why; see git history for the actual changes.
>
> **Superseded install-surface note:** The repository was later reorganized into grouped install surfaces on 2026-06-23. Current grouping lives in `.claude-plugin/marketplace.json`, `skills.sh.json`, [README.md](../../README.md), and [CLAUDE.md](../../CLAUDE.md). The historical "six skills" counts below describe the 2026-05-22 state, before `simplify-code`, `core-dev`, and the `olegvg-skills` umbrella existed.

**Goal:** Make `npx skills add olegvg/kb-for-agents` install this plugin's runtime skills cleanly across every agent supported by [vercel-labs/skills](https://github.com/vercel-labs/skills), without breaking the existing Claude Code plugin or Codex marketplace paths.

**Architecture:** The vercel-labs/skills CLI discovers `SKILL.md` files at standard paths — first-class is `skills/<name>/SKILL.md`, which we already use. Plugin-manifest discovery also reads `.claude-plugin/marketplace.json` `plugins[].skills` for explicit declarations. The work was: fix one strict-YAML bug, rewrite slash-command syntax in `kb-maintain` so it stays portable, document the third install pathway in READMEs and `CLAUDE.md`, declare skills explicitly in the marketplace manifest, and dogfood the result.

**Tech Stack:** Markdown only. YAML 1.2 frontmatter per [agentskills.io](https://agentskills.io). `npx skills` CLI (Node 18+) for verification.

---

## What was executed

### Task 1 — Audit (`npx skills add ./ --list`)

Ran the real installer against the local checkout. It reported **5 skills, not 6** — `kb-maintain` was silently dropped. Root cause: the `description` value contained the substring `pass over .kb/: check drift` — the colon-space `: ` is a YAML 1.2 key-value separator. Claude Code's lenient YAML parser accepts it; the CLI's strict parser does not, and drops the skill without error.

### Task 2, Task 3 — SKIPPED

Before execution started, the user deleted `skills/kb-demo/`, `skills/kb-bench/`, `commands/kb-demo.md`, `commands/kb-bench.md`, `examples/`, and `benchmarks/` and updated the READMEs to drop their references. Tasks 2 and 3 from the original plan (which were going to mark those skills `metadata.internal: true`) became no-ops.

### Task 4 — Fix `kb-maintain`

Two edits to `skills/kb-maintain/SKILL.md`:

1. **YAML fix:** replaced `pass over .kb/: check drift,` with `pass over .kb/ — check drift,` in the `description` frontmatter field. The em-dash carries the same meaning and parses cleanly under strict YAML.
2. **Slash-command syntax fix:** rewrote four references from `/kb-build` / `/kb-refresh` / `/kb-record-decision` slash-command style to `the <skill> skill` natural-language references. A single parenthetical fallback to `/kb-build` was kept so Claude Code plugin users still see the convenience syntax. Rationale: when the plugin is installed via `npx skills add`, slash commands don't exist — only skills do. Orchestrators must address siblings by skill name, not by slash command.

### Task 5 — README.md

- Added a new `### Any agent via npx skills add (vercel-labs/skills CLI)` section between Codex marketplace and Claude Desktop, with copy-pasteable install commands and a clear callout that slash commands are not installed by this pathway.
- Annotated the "Commands" line under "What's inside" with `*(Claude Code only — installed via the plugin pathway, not via npx skills add.)*` so the limitation is visible up front.

### Task 6 — README.ru.md

Mirrored Task 5 in Russian. Same structural placement, same wording with "skills/skill" left in English (matches the rest of the file's voice).

### Task 7 — CLAUDE.md

Four edits:

1. Updated the install snippet at the top to show both `/plugin install` and `npx skills add` pathways.
2. Added a new `## Two install pathways, one source of truth` section listing the practical consequences for future skill edits: don't assume sibling `commands/<x>.md` exists; don't depend on repo-bundled assets without marking `metadata.internal: true`; avoid unquoted `: ` in `description` values (the bug that broke Task 1).
3. Extended the "When adding a new skill" checklist with two new steps: declare the skill in `.claude-plugin/marketplace.json`, and set `metadata.internal: true` when the skill needs bundled assets.
4. Appended a note to "Verifying changes" to also run `npx skills add ./ --list` as part of dogfooding — strict YAML parse failures only surface there.

### Task 8 — `.claude-plugin/marketplace.json`

Added an explicit `skills` array to the single plugin entry, listing all six portable runtime skills by path. This gives the CLI's plugin-manifest discovery an authoritative list independent of filename scanning, and makes the marketplace manifest the place new contributors update when adding a skill.

### Task 9 — End-to-end dogfood

Installed the six skills into a throwaway `/tmp/kb-dogfood` git repo via `npx -y skills@latest add … -a claude-code -y --copy`. All six landed under `.claude/skills/`. `grep '/kb-'` against the installed `kb-maintain` showed only the intentional parenthetical fallback and three relative file-path references in the References section — no stray slash-command instructions. Scratch dir cleaned up.

---

## Key finding worth remembering

**Strict YAML parses `: ` as a key-value separator inside unquoted scalars.** Claude Code is lenient and will swallow constructs like `description: ... over .kb/: check drift`, but the vercel-labs/skills CLI uses `yaml@^2` which is strict per YAML 1.2, and silently drops the skill from discovery. There's no error message — the skill just doesn't appear in the listing.

Mitigation now codified in `CLAUDE.md`: avoid unquoted `: ` in `description` values, and run `npx skills add ./ --list` as part of dogfooding so this fails loudly the next time it happens.

---

## What is intentionally NOT done

- **Publishing to skills.sh / vercel-labs/agent-skills directory** — separate submission, out of scope.
- **Renaming `commands/` or relocating skills** — the existing structure already matches both pathways. No moves needed.
- **Version bump in `plugin.json` / `marketplace.json`** — left for a release commit.
- **Reordering README install sections to lead with `npx skills add`** — Task 10 from the original plan. Left for the maintainer to decide.

---

## Verification — final state

```
$ npx -y skills@latest add ./ --list
Found 6 skills
  kb-build, kb-check-drift, kb-maintain, kb-query, kb-record-decision, kb-refresh

$ # Dogfood install (see Task 9)
$ ls /tmp/kb-dogfood/.claude/skills/
kb-build  kb-check-drift  kb-maintain  kb-query  kb-record-decision  kb-refresh
```

All six runtime skills are now installable via the vercel-labs/skills CLI into any of its 50+ supported agents. The Claude Code plugin pathway (`/plugin install`) and the Codex marketplace pathway are unchanged.
