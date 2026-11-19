# AGENTS.md

Guidance for Claude Code, Codex, and other coding agents working in this repository.

## What This Repo Is

A grouped personal skill repository for Claude Code, Codex, and Vercel Skills CLI. The root instruction package ships skills, commands, templates, docs and install manifests. Python 3.10+ standard-library tooling validates and builds releases; the independent audio plugin retains its own Python runtime and tests.

## Always-On Rules

- `.kb/` lives inside the user's corpus, never inside this plugin. Any change that couples `.kb/` to this plugin location is wrong.
- Runtime skills under `skills/` are the source of truth for the `olegvg-skills` umbrella package. A standalone plugin under `plugins/<plugin-name>/` is self-contained and is exposed by paired manifests: `.codex-plugin/plugin.json` plus an entry in `.agents/plugins/marketplace.json` for Codex, and `.claude-plugin/plugin.json` plus an entry in the root `.claude-plugin/marketplace.json` for Claude Code.
- `kb-for-agents` must stay KB-only. General-purpose skills belong in `core-dev` or a future non-KB group.
- Every public root skill under `skills/` belongs to exactly one concrete group in `.claude-plugin/marketplace.json` and also appears in the `olegvg-skills` umbrella entry. Skills bundled inside a standalone plugin are owned by that plugin and must not be duplicated in the root groups or any `skills` array — they cannot work without the plugin runtime.
- Concrete Claude groups source `./skills` and expose native namespaced skill commands; only the umbrella retains root command shims. Use `strict: true` to avoid current Claude manifest conflicts.
- Vercel Skills CLI can show only one visible group per skill. Keep the umbrella entry first and concrete groups after it; umbrella install is `--skill '*'` or selecting all concrete groups interactively.
- `CLAUDE.md` is a symlink to this file. Update `AGENTS.md`; do not create divergent Claude-only instructions.
- Root `plugin.json` owns umbrella metadata. Keep host manifests and marketplace identity aligned. A prepared version is not published; commits, tags, pushes, publication and real/global installation require explicit user authorization. Verify installations only in disposable projects/configuration directories.
- Release inputs are explicitly listed in `scripts/release_inventory.py`. Never package private corpus files, generated KBs, audio/transcripts, credentials, model/runtime caches, tests or development plans. Keep SECURITY.md and PRIVACY.md accurate.

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
| `core-dev` | General development workflow skills | `simplify-code`, `mobile-test-environments`, `deep-code-review` |
| `olegvg-skills` | Umbrella package | every public runtime skill in this repository |
| `transcribing-audio` | Standalone audio-transcription plugin (Claude Code and Codex), not part of the umbrella | bundled `transcribing-audio` skill plus its Python runtime |

## Repo Layout

- `plugin.json` — canonical Agent Plugins 1.0.0 umbrella identity.
- `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` — Claude Code plugin and marketplace manifests; `.claude-plugin/marketplace.json` also drives Vercel Skills CLI grouping.
- `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json` — Codex umbrella plugin and self-hosted marketplace index.
- `plugins/<name>/` — self-contained independently installable plugins for Claude Code and Codex, each with its own paired manifests, runtime, tests, and marketplace entries.
- `skills.sh.json` — skills.sh website grouping only.
- `skills/<name>/SKILL.md` — portable skill sources with strict YAML frontmatter and English/Russian trigger phrases.
- `commands/<name>.md` — Claude Code slash-command shims only; keep them thin.
- `skills/kb-build/templates/` — canonical build templates included in skill-only installs. `templates/README.md` links there for manual users.
- `scripts/`, `tests/`, `.github/workflows/` — validated reproducible builds, release-boundary tests and CI/publication workflows.
- `docs/` — rationale, plans, and progressive-disclosure instructions.

## Dogfood Commands

```bash
# Claude Code plugin marketplace
/plugin marketplace add olegvg/olegvg-skills
/plugin install kb-for-agents@olegvg-skills
/plugin install core-dev@olegvg-skills
/plugin install olegvg-skills@olegvg-skills
/plugin install transcribing-audio@olegvg-skills

# Vercel Skills CLI / any supported agent
npx skills add olegvg/olegvg-skills --list
npx skills add olegvg/olegvg-skills --skill simplify-code -a codex

# Local uncommitted checkout
npx skills add ./ --list
```

## Verification

Run `python3 scripts/validate_plugin.py`, `python3 -m unittest discover -s tests -v`,
`git diff --check` and a preview build with a fresh output directory outside the
checkout. For installer changes also run `bunx skills@latest install ./ --list`
and verify actual copied skill contents in a disposable project. Validate explicit
Claude manifests and the marketplace; source CLAUDE.md may warn, so validate the
extracted runtime ZIP strictly too. See [docs/releasing.md](docs/releasing.md) for
complete checks, deterministic output, Git boundaries and release authorization.
