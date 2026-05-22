# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A Claude Code and Codex plugin — **markdown only, no build system, no test suite, no package manager**. The deliverable is a set of skills, commands, templates, and docs. "Running" this repo means installing it as a plugin and invoking its skills or slash commands against a target corpus.

Install locally to dogfood changes:

```
# Claude Code (plugin — skills + slash commands)
/plugin marketplace add olegvg/kb-for-agents
/plugin install kb-for-agents@kb-for-agents

# Any agent (skills only, via vercel-labs/skills CLI)
npx skills add olegvg/kb-for-agents
```

## Critical architectural invariant

**`.kb/` lives inside the user's corpus, never inside this plugin.** The plugin is stateless with respect to any specific corpus. A user must be able to copy `.kb/` between machines or check it into their own repo alongside their code. If a change to a skill or template would couple `.kb/` to this plugin's location, that change is wrong. This is non-negotiable — it's what makes the pattern survive the plugin.

## The three-layer pattern this plugin encodes

1. **Sources** — the corpus itself. Never duplicated.
2. **Summaries** (`.kb/summaries/<area>/*.md`) — prose, one topic per file, freeform size.
3. **Indexes** (`.kb/indexes/*.md`) — navigation, **≤300 tokens per file**, signposts only, no prose. Entry point `.kb/indexes/_root.md`.

Plus **decisions** (`.kb/decisions/*.md`) — distilled records from completed plans. Decisions are NOT a fourth layer and never appear as a top-level area in `_root.md`. The link between a decision and the summaries it affects lives in the decision record's `## Affected areas` block — summaries themselves are never edited when a decision is recorded. Agents find decisions for a summary by greping `.kb/decisions/` for the summary's path; `kb-query` does this lookup automatically.

Why three layers: progressive disclosure. See [docs/concept.md](docs/concept.md).

## Two install pathways, one source of truth

The runtime skills under `skills/` are the source of truth. They install through:

1. `/plugin install kb-for-agents@kb-for-agents` — Claude Code plugin pathway. Installs skills **and** the slash commands under `commands/`. This is the dogfood path.
2. `npx skills add olegvg/kb-for-agents` — [vercel-labs/skills](https://github.com/vercel-labs/skills) CLI pathway. Installs skills into any of 50+ agents (Claude Code, Codex, Cursor, OpenCode, …). Does **not** install slash commands.

When editing a skill or adding a new one, both pathways must keep working. Two practical consequences:

- A skill's body must not assume a sibling `commands/<x>.md` exists. Refer to sibling skills by name (e.g., "invoke the `kb-refresh` skill"), not by `/<command>` syntax. A parenthetical fallback to `/<command>` is fine.
- A skill must not depend on assets that don't ship inside its own directory. The `npx skills add` CLI installs `skills/<name>/` only; sibling repo directories (templates, examples, benchmarks) are not bundled. If a skill needs bundled assets and cannot be made standalone, mark it `metadata.internal: true` in the frontmatter — the CLI will then hide it from default discovery (override via `INSTALL_INTERNAL_SKILLS=1`).
- YAML frontmatter must be valid under strict YAML 1.2. Avoid unquoted `: ` (colon-space) inside `description` values — strict parsers (such as the one the `skills` CLI uses) treat it as a key-value separator and drop the skill. Claude Code's parser is lenient and will still load it, so this fails silently on the cross-agent install path. Use `—` or rephrase to remove `: `.

## Repo layout

- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` — Claude Code plugin and self-hosted marketplace manifests. Version bumps go here.
- `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json` — Codex plugin and self-hosted marketplace manifests. Keep metadata in sync with the Claude manifests.
- `skills/<name>/SKILL.md` — each skill is a single markdown file with YAML frontmatter (`name`, `description`). The `description` field is what Claude Code matches against to auto-invoke the skill; it must include trigger phrases (English + Russian in this repo).
- `commands/<name>.md` — thin slash-command wrappers. Each one is essentially `Invoke the <name> skill with $ARGUMENTS`. Do not duplicate skill logic into the command file.
- `templates/` — starter shapes for `_root.md`, area indexes, summaries, decisions. Referenced by the skills. Users can also hand-copy them (see [templates/README.md](templates/README.md)).
- `docs/` — pattern rationale. [concept.md](docs/concept.md), [navigation-rules.md](docs/navigation-rules.md), [refresh-strategy.md](docs/refresh-strategy.md). These drive the skills, not the reverse — if you change a skill's behavior, check whether the corresponding doc still holds, and update the doc if not.

## The skills and how they relate

| Skill | Mode | Writes `.kb/`? | Writes `.kb-state.json`? |
|---|---|---|---|
| `kb-build` | one-shot, fresh build | yes (creates) | yes (initializes) |
| `kb-query` | read-only | no | no |
| `kb-refresh` | scoped, manual | yes (updates) | yes (advances `last_linted_sha`) |
| `kb-check-drift` | read-only | **no** | **no** |
| `kb-record-decision` | manual, post-plan | yes (adds decision only — never edits summaries) | no |
| `kb-maintain` | orchestrated, manual | delegates only | delegates only |

The `kb-check-drift` / `kb-refresh` split is deliberate — drift detection is read-only and reports candidates; only `kb-refresh` mutates and advances state. Never collapse them. See [docs/refresh-strategy.md](docs/refresh-strategy.md).

`kb-build` uses a strict three-pass workflow (survey → parallel subagent deep-build → main-agent index assembly). The main agent never reads full file bodies in passes 1 or 3 — that is the context-window guarantee of the pattern. Do not collapse the passes even on small corpora.

## When editing skills

- Preserve the YAML frontmatter shape. `name` must match the directory, `description` drives auto-invocation.
- Keep the trigger-phrase list in `description` (English + Russian). Removing triggers breaks auto-invocation for existing users.
- The **300-token index budget is a hard limit**, not a suggestion. If you relax it in a skill, update [docs/concept.md](docs/concept.md) and [docs/navigation-rules.md](docs/navigation-rules.md) too.
- The `kb-check-drift` heuristic is policy, not code — it lives as a checklist in [skills/kb-check-drift/SKILL.md](skills/kb-check-drift/SKILL.md). That's the intended extension point. Do not add config files or YAML schemas for it.

## When adding a new skill

1. Create `skills/<name>/SKILL.md` with frontmatter (`name`, `description` with trigger phrases). Keep `description` free of unquoted `: ` to stay parseable by strict YAML.
2. Create `commands/<name>.md` as a thin wrapper invoking the skill with `$ARGUMENTS`.
3. Update the "What's inside" and "Quickstart" sections in [README.md](README.md) and [README.ru.md](README.ru.md).
4. If the skill represents a new pattern concept, add rationale to `docs/` — don't bury it only in the skill file.
5. Add the new skill to the `skills` array in `.claude-plugin/marketplace.json` so plugin-manifest discovery sees it explicitly.
6. If the skill depends on assets bundled inside this repo (e.g., demo corpora, benchmarks), set `metadata.internal: true` in its frontmatter so `npx skills add` does not expose a broken standalone skill.

## Verifying changes

No automated tests. Verification is by reading:
- Do the skill files still match the rationale in `docs/`?
- Do the commands still one-line-wrap the skills?
- Does the README's Quickstart still work against a throwaway corpus?

For behavior changes, dogfood against a real corpus via `/plugin install` before committing. Also run `npx skills add ./ --list` to confirm every runtime skill is still picked up by the cross-agent CLI — strict YAML parse errors only surface there.
