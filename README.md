# OlegVG Skills

[Русская версия](README.ru.md)

A grouped personal skill repository for Claude Code, Codex, and agents supported by the Vercel Skills CLI. It ships two installable root-skill groups: `kb-for-agents` for the three-layer knowledge base pattern described in [Knowledge Base for Agents](https://www.linkedin.com/posts/ahaidukof_karpathy-%D1%84%D0%BE%D1%80%D0%BC%D0%B0%D0%BB%D0%B8%D0%B7%D0%BE%D0%B2%D0%B0%D0%BB-%D1%82%D0%BE-%D1%87%D1%82%D0%BE-%D0%BC%D1%8B-%D0%BD%D0%B0%D1%89%D1%83%D0%BF%D0%B0%D0%BB%D0%B8-activity-7446836637143130112-o920/) and `core-dev` for portable development workflows, plus the standalone Codex plugin `transcribing-audio`.

## What's inside

- **`kb-for-agents` group** — `kb-build`, `kb-query`, `kb-check-drift`, `kb-refresh`, `kb-record-decision`, `kb-maintain`.
- **`core-dev` group** — `simplify-code`, a portable behavior-preserving cleanup skill adapted from Claude Code's `/simplify` workflow.
- **`olegvg-skills` umbrella** — all groups in this repository.
- **`transcribing-audio` Codex plugin** — local or OpenAI ASR, speaker diarization, word timestamps, and resumable processing. It is installed separately because it includes its own Python runtime and dependencies.
- **Commands** — `/kb-build`, `/kb-query`, `/kb-check-drift`, `/kb-refresh`, `/kb-record-decision`, `/kb-maintain`. Thin wrappers over the skills. *(Claude Code only — installed via the plugin pathway, not via `npx skills add`.)*
- **Templates** — starter shapes for indexes, summaries, decisions, `_root.md`, state. See [templates/README.md](templates/README.md) for manual-build steps.
- **Docs** — pattern rationale: [concept](docs/concept.md), [navigation rules](docs/navigation-rules.md), [refresh strategy](docs/refresh-strategy.md).

## Install

### Any agent via `npx skills add` (Vercel Skills CLI)

The runtime skills follow the [agentskills.io](https://agentskills.io) spec and can be installed into Claude Code, Codex, Cursor, and other agents through the [`skills` CLI](https://github.com/vercel-labs/skills). The interactive picker shows the concrete groups `kb-for-agents` and `core-dev`; select both groups to install everything. For non-interactive installs, use explicit `--skill` selections. The umbrella install is `--skill '*'` because the CLI currently assigns each skill to one visible group.

```bash
# List grouped skills in the repo
npx skills add olegvg/olegvg-skills --list

# Install the kb-for-agents group
npx skills add olegvg/olegvg-skills \
  --skill kb-build \
  --skill kb-query \
  --skill kb-refresh \
  --skill kb-check-drift \
  --skill kb-record-decision \
  --skill kb-maintain

# Install the core-dev group
npx skills add olegvg/olegvg-skills --skill simplify-code

# Install the umbrella package non-interactively
npx skills add olegvg/olegvg-skills --skill '*'

# Install core-dev into Codex globally
npx skills add olegvg/olegvg-skills --skill simplify-code -a codex -g -y

# Install across multiple agents at once
npx skills add olegvg/olegvg-skills -a claude-code -a codex -a cursor
```

This pathway installs **skills only**, not slash commands. The Claude Code `/kb-*` commands are available only via the `/plugin install` route below. Skills are still auto-invoked by trigger phrases — see each skill's `description` for the English and Russian phrases that activate it.

### Claude Code plugin marketplace

```
/plugin marketplace add olegvg/olegvg-skills
/plugin install kb-for-agents@olegvg-skills
/plugin install core-dev@olegvg-skills
/plugin install olegvg-skills@olegvg-skills
```

Use `kb-for-agents` when you want the `/kb-*` commands alongside the KB skills, `core-dev` for the portable cleanup skill, or `olegvg-skills` for everything in this repository.

Unlike the Vercel Skills CLI picker, the Claude Code plugin marketplace has a real umbrella install target: `olegvg-skills@olegvg-skills`.

### Codex marketplace

This repository is packaged for Codex as the umbrella `olegvg-skills` plugin and as the independent `transcribing-audio` plugin:

- `.codex-plugin/plugin.json` — Codex plugin manifest.
- `.agents/plugins/marketplace.json` — self-hosted Codex marketplace index pointing at this plugin repository.

Codex loads the umbrella skills from `skills/`. Use the Vercel Skills CLI with `-a codex` for group-scoped Codex installs. Install audio transcription as its own plugin from the marketplace:

```bash
codex plugin marketplace add olegvg/olegvg-skills
codex plugin add transcribing-audio@olegvg-skills
```

`transcribing-audio` keeps its runtime and dependencies in `plugins/transcribing-audio/`; the `commands/` directory remains for Claude Code slash-command compatibility.

### Claude Desktop (individual skills)

Claude Desktop doesn't load Claude Code plugins, so runtime skills are published as individual zips on the [Releases page](https://github.com/olegvg/olegvg-skills/releases). Download and upload the ones you need via the Claude Desktop skill UI:

- `kb-build-<version>.zip`
- `kb-query-<version>.zip`
- `kb-refresh-<version>.zip`
- `kb-check-drift-<version>.zip`
- `simplify-code-<version>.zip`

`SHA256SUMS` is attached to each release — verify with `sha256sum -c SHA256SUMS`.

`kb-record-decision` and `kb-maintain` are Claude Code–only: decision recording relies on the plan-document layout and orchestration.

## Quickstart

In any Claude Code session opened at your corpus root:

```
/kb-build .
/kb-query where are fees charged?
```

After you've made changes to the corpus:

```
/kb-check-drift
/kb-refresh src/billing/
```

When a planned piece of work ships and you want its key choices preserved:

```
/kb-record-decision docs/plans/2026-03-19-1400/plan-billing-rewrite.md
```

## How it works

The plugin builds a `.kb/` directory **inside your corpus** (not inside the plugin). It has three layers plus a decisions store:

1. **Sources** — your corpus itself. Not duplicated.
2. **Summaries** (`.kb/summaries/<area>/*.md`) — prose per topic, one file each.
3. **Indexes** (`.kb/indexes/*.md`) — navigation, ≤300 tokens per file. Entry point is `.kb/indexes/_root.md`.

Alongside: **Decisions** (`.kb/decisions/*.md`) — distilled records extracted from completed plans. Each record names the summaries it affects in its own `## Affected areas` block; summaries themselves are never edited when a decision is recorded. Agents find decisions for a summary by greping `.kb/decisions/` for that summary's path; `kb-query` does this lookup automatically.

The agent reads indexes first on any query, then descends. If the question is "how does X work, and why was it built that way?", the navigation lands on a summary, and the decisions backreferenced from that summary surface in the same pass. Context stays bounded and the navigation path is reviewable.

See [docs/concept.md](docs/concept.md) for the full argument.

## What this is

A starter kit: skills, commands, templates, conceptual docs. Patterns codified so you can apply them without re-reading the article.

## What this is not

A RAG library or a general-purpose agent framework.

## Requirements

- Claude Code or Codex with skills support.
- A corpus you want to document. A git-backed corpus is strongly recommended — `/kb-refresh` and `/kb-check-drift` both depend on git history.

## License

MIT. See [LICENSE](LICENSE).
