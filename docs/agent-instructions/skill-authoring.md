# Skill Authoring

Use this before adding or editing skills, groups, command shims, or skill packaging metadata.

## Editing Existing Skills

- Preserve YAML frontmatter shape. `name` must match the directory.
- Keep trigger phrases in `description`, including English and Russian triggers where the skill already has them.
- Avoid unquoted `: ` in `description`; strict YAML 1.2 parsers can treat it as a key-value separator and drop the skill from Vercel Skills CLI discovery.
- A skill body must not assume a sibling `commands/<name>.md` exists. Refer to sibling skills by name, not by slash command. A parenthetical slash-command fallback is fine for Claude Code users.
- A skill must not depend on repo sibling assets unless those assets are bundled inside the skill directory or the skill is marked `metadata.internal: true`.

## Adding a New Skill

1. Create `skills/<name>/SKILL.md` with frontmatter: `name`, `description`, and trigger phrases.
2. Add `skills/<name>/agents/openai.yaml` only when Codex-specific interface metadata is useful.
3. Create `commands/<name>.md` only when a Claude Code slash-command shim is required for migration or compatibility. Keep it as a thin wrapper invoking the skill with `$ARGUMENTS`.
4. Assign the skill to exactly one concrete group in `.claude-plugin/marketplace.json`.
5. Also add the skill to the `olegvg-skills` umbrella entry in `.claude-plugin/marketplace.json`.
6. Add the skill to the matching group in `skills.sh.json`.
7. If the skill changes the user-visible surface, update [../../README.md](../../README.md), [../../README.ru.md](../../README.ru.md), and [../../AGENTS.md](../../AGENTS.md) routing/group summaries as needed.
8. If the skill introduces a new pattern concept, add or update rationale under `docs/` instead of burying the rationale only in the skill file.

## Adding a New Group

1. Add a concrete group entry to `.claude-plugin/marketplace.json` with `name`, `description`, `version`, `source`, `author`, `strict: false`, and explicit `skills` and `commands` arrays. When several groups use `source: "./"`, this prevents the default `commands/` scan from leaking command shims into an unrelated group; use `"commands": []` for a group with no shims.
2. Keep the `olegvg-skills` umbrella entry first, then list concrete groups after it.
3. Add the group to `skills.sh.json` so website grouping matches CLI grouping.
4. Update README install examples and the install group table in `AGENTS.md`.
5. Update `.codex-plugin/plugin.json` only at the umbrella-copy level. Do not invent unsupported Codex group fields.

## Standalone Install Constraint

Vercel Skills CLI installs a selected root `skills/<name>/` directory only. It does not include `templates/`, sibling skills, examples, benchmarks, commands, or a plugin runtime. If a skill needs any of those at runtime, either bundle everything inside the skill directory, mark the skill internal, or make it a standalone plugin.

## Standalone Runtime Plugins

Use `plugins/<name>/` for a capability that cannot work as a root skill alone, such as `transcribing-audio` with its Python runtime. A standalone plugin must have its bundled `skills/`, runtime, and tests under the same directory, plus paired Claude Code and Codex manifests. Add marketplace entries that point to the plugin root, but never add its bundled skill to a root group, an umbrella `skills` array, or `skills.sh.json`. Update both READMEs and [install-surfaces.md](install-surfaces.md) with the marketplace-only installation path.

## Current Concrete Groups

- `kb-for-agents`: `kb-build`, `kb-query`, `kb-refresh`, `kb-check-drift`, `kb-record-decision`, `kb-maintain`.
- `core-dev`: `simplify-code`.

General-purpose skills do not belong in `kb-for-agents`.
