# AGENTS.md

Guidance for Claude Code, Codex, and other coding agents working in this repository.

## What This Repo Is

A grouped personal skill repository for Claude Code, Codex, and Vercel Skills CLI. It is markdown-only: no build system, no test suite, no package manager. The deliverable is skills, commands, templates, docs, and install manifests.

## Always-On Rules

- `.kb/` lives inside the user's corpus, never inside this plugin. Any change that couples `.kb/` to this plugin location is wrong.
- Runtime skills under `skills/` are the source of truth for the `olegvg-skills` umbrella package. A standalone Codex plugin under `plugins/<plugin-name>/` is self-contained and is exposed by its own `.codex-plugin/plugin.json` plus an entry in `.agents/plugins/marketplace.json`.
- `kb-for-agents` must stay KB-only. General-purpose skills belong in `core-dev` or a future non-KB group.
- Every public root skill under `skills/` belongs to exactly one concrete group in `.claude-plugin/marketplace.json` and also appears in the `olegvg-skills` umbrella entry. Skills bundled inside a standalone Codex plugin are owned by that plugin and must not be duplicated in the root groups.
- Vercel Skills CLI can show only one visible group per skill. Keep the umbrella entry first and concrete groups after it; umbrella install is `--skill '*'` or selecting all concrete groups interactively.
- `CLAUDE.md` is a symlink to this file. Update `AGENTS.md`; do not create divergent Claude-only instructions.
- Every version bump requires a matching pushed git tag, e.g. manifest `0.6.0` must ship with tag `v0.6.0`; the desktop release workflow depends on tag pushes.

## Progressive Disclosure

Read only the file needed for the task before editing:

- Before changing install commands, plugin manifests, marketplace metadata, or skills.sh grouping, read [docs/agent-instructions/install-surfaces.md](docs/agent-instructions/install-surfaces.md).
- Before adding or editing skills, groups, command shims, or skill packaging metadata, read [docs/agent-instructions/skill-authoring.md](docs/agent-instructions/skill-authoring.md).
- Before changing `kb-*` behavior, templates, or KB rationale docs, read [docs/agent-instructions/kb-pattern.md](docs/agent-instructions/kb-pattern.md).
- Before bumping versions, tagging releases, or changing release packaging, read [docs/agent-instructions/release-versioning.md](docs/agent-instructions/release-versioning.md).

## Current Install Groups

| Group | Purpose | Skills |
|---|---|---|
| `kb-for-agents` | Three-layer KB management | `kb-build`, `kb-query`, `kb-refresh`, `kb-check-drift`, `kb-record-decision`, `kb-maintain` |
| `core-dev` | General development workflow skills | `simplify-code` |
| `olegvg-skills` | Umbrella package | every public runtime skill in this repository |

## Repo Layout

- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` — Claude Code plugin and marketplace manifests; `.claude-plugin/marketplace.json` also drives Vercel Skills CLI grouping.
- `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json` — Codex umbrella plugin and self-hosted marketplace index.
- `plugins/<name>/` — self-contained independently installable Codex plugins, each with its own manifest, runtime, tests, and marketplace entry.
- `skills.sh.json` — skills.sh website grouping only.
- `skills/<name>/SKILL.md` — portable skill sources with strict YAML frontmatter and English/Russian trigger phrases.
- `commands/<name>.md` — Claude Code slash-command shims only; keep them thin.
- `templates/` — starter shapes for KB indexes, summaries, decisions, root, and state.
- `docs/` — rationale, plans, and progressive-disclosure instructions.

## Dogfood Commands

```bash
# Claude Code plugin marketplace
/plugin marketplace add olegvg/olegvg-skills
/plugin install kb-for-agents@olegvg-skills
/plugin install core-dev@olegvg-skills
/plugin install olegvg-skills@olegvg-skills

# Vercel Skills CLI / any supported agent
npx skills add olegvg/olegvg-skills --list
npx skills add olegvg/olegvg-skills --skill simplify-code -a codex

# Local uncommitted checkout
npx skills add ./ --list
```

## Verification

There is no automated project test suite. For most changes, verify by validating JSON manifests, running `git diff --check`, and reading affected docs/skills for consistency. For installer-facing changes, also run `npx skills add ./ --list` against the local checkout.
