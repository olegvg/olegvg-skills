# Skill Group Install Surfaces Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose this repository as installable skill groups: `kb-for-agents`, `core-dev`, and umbrella `olegvg-skills`.

**Architecture:** Keep skill sources under the existing `skills/<name>/` layout. Use `.claude-plugin/marketplace.json` as the explicit group manifest for Claude Code marketplace and Vercel Skills CLI discovery, keep Codex metadata as an umbrella package, and add `skills.sh.json` for the skills.sh repository page grouping.

**Tech Stack:** Markdown skills, JSON manifests, GitHub Actions YAML.

## Global Constraints

- `.kb/` must remain a user's corpus artifact, never plugin state.
- `kb-for-agents` must contain only `kb-*` skills and existing `/kb-*` commands.
- `core-dev` must contain `simplify-code` and no slash-command shim.
- `olegvg-skills` must install or describe all runtime skills.
- Preserve strict YAML frontmatter compatibility in every `SKILL.md`.
- There is no build system or test suite; verify by JSON validation, manifest inspection, and installer-facing listing when possible.

---

### Task 1: Group Manifests

**Files:**
- Modify: `.claude-plugin/marketplace.json`
- Modify: `.claude-plugin/plugin.json`
- Modify: `.codex-plugin/plugin.json`
- Modify: `.agents/plugins/marketplace.json`

**Interfaces:**
- Consumes: existing skill paths under `skills/`.
- Produces: explicit install groups `kb-for-agents`, `core-dev`, and `olegvg-skills`.

- [x] Reset KB-only descriptions so `kb-for-agents` is not described as containing `simplify-code`.
- [x] Add `core-dev` to `.claude-plugin/marketplace.json` with only `./skills/simplify-code`.
- [x] Add `olegvg-skills` to `.claude-plugin/marketplace.json` with all runtime skills.
- [x] Change Codex plugin metadata to describe umbrella `olegvg-skills` while naming the two groups in user-facing copy.
- [x] Keep the Codex marketplace entry as the umbrella install because one `.codex-plugin/plugin.json` describes one plugin root; grouped Codex installs are exposed through the Vercel Skills CLI target.

### Task 2: Vercel Skills Page Grouping

**Files:**
- Create: `skills.sh.json`

**Interfaces:**
- Consumes: skills.sh grouping schema.
- Produces: display groups `KB for Agents` and `Core Dev`.

- [x] Add `skills.sh.json` with `notGrouped: "bottom"`.
- [x] List the six `kb-*` skills in the KB group.
- [x] List `simplify-code` in the Core Dev group.

### Task 3: Documentation

**Files:**
- Modify: `README.md`
- Modify: `README.ru.md`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: group names from Task 1.
- Produces: installation guidance that distinguishes group install from umbrella install.

- [x] Update the repo description to explain that this is now a personal skill repository with grouped install surfaces.
- [x] Document Vercel Skills CLI install examples for `kb-for-agents`, `core-dev`, and `olegvg-skills`.
- [x] Keep Claude Code slash-command guidance scoped to `kb-for-agents`.
- [x] Update maintainer guidance so future skills are assigned to a group and marketplace manifests stay synchronized.

### Task 4: Claude Desktop Packaging

**Files:**
- Modify: `.github/workflows/release-desktop-skills.yml`

**Interfaces:**
- Consumes: standalone desktop-compatible skills.
- Produces: release zips that match README promises.

- [x] Add `simplify-code` to the packaged `SKILLS` list.
- [x] Keep `kb-record-decision` and `kb-maintain` excluded from desktop packaging.

### Task 5: Verification

**Files:**
- Read: changed manifest and docs files.

**Interfaces:**
- Consumes: final file contents.
- Produces: command evidence for completion.

- [x] Run JSON validation for every changed JSON manifest and `skills.sh.json`.
- [x] Run `git diff --check`.
- [x] Run `npx skills add ./ --list` if the CLI is available; if network access blocks it, record that limitation.
- [x] Review `git diff --stat` and ensure unrelated files were not changed.
