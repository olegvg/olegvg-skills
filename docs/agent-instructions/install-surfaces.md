# Install Surfaces

Use this before changing install commands, plugin manifests, marketplace metadata, skills.sh grouping, or README install sections.

## Source of Truth

Runtime skills live under `skills/`. Install surfaces are metadata over those source directories:

1. Claude Code plugin marketplace uses `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`.
2. Vercel Skills CLI reads `SKILL.md` files and `.claude-plugin/marketplace.json` `plugins[].skills` declarations.
3. Codex marketplace uses `.codex-plugin/plugin.json` and `.agents/plugins/marketplace.json`.
4. skills.sh website grouping uses `skills.sh.json` only.

## Manifests to Keep in Sync

- `.claude-plugin/plugin.json` describes the Claude Code umbrella plugin.
- `.claude-plugin/marketplace.json` contains concrete install groups plus the umbrella entry.
- `.codex-plugin/plugin.json` describes the Codex umbrella plugin. Do not add unsupported group fields.
- `.agents/plugins/marketplace.json` exposes the Codex umbrella plugin in the self-hosted marketplace index.
- `skills.sh.json` mirrors public grouping for the website.

## Claude Code

Claude Code has real plugin install targets from `.claude-plugin/marketplace.json`:

```text
/plugin marketplace add olegvg/olegvg-skills
/plugin install kb-for-agents@olegvg-skills
/plugin install core-dev@olegvg-skills
/plugin install olegvg-skills@olegvg-skills
```

`kb-for-agents` installs the KB skills and `/kb-*` slash commands. `core-dev` installs portable development skills such as `simplify-code`; it has no slash-command shim. `olegvg-skills` installs everything.

## Codex

Codex marketplace packaging is the umbrella `olegvg-skills` plugin. One `.codex-plugin/plugin.json` describes one plugin root, so group-scoped Codex marketplace entries are not represented as separate plugin manifests.

For a group-scoped Codex install, use Vercel Skills CLI with `-a codex`, for example:

```bash
npx skills add olegvg/olegvg-skills --skill simplify-code -a codex
```

## Vercel Skills CLI

Vercel Skills CLI installs skills only. It does not install Claude Code slash commands from `commands/`.

Interactive picker behavior:

- It shows concrete groups such as `Core Dev` and `Kb For Agents`.
- It cannot show the same skill in a concrete group and a visible umbrella group at the same time.
- To install everything interactively, select all concrete groups.

Non-interactive examples:

```bash
# List grouped skills from remote state
npx skills add olegvg/olegvg-skills --list

# Test local uncommitted checkout
npx skills add ./ --list

# Install the KB group
npx skills add olegvg/olegvg-skills   --skill kb-build   --skill kb-query   --skill kb-refresh   --skill kb-check-drift   --skill kb-record-decision   --skill kb-maintain

# Install the core-dev group
npx skills add olegvg/olegvg-skills --skill simplify-code

# Install everything non-interactively
npx skills add olegvg/olegvg-skills --skill '*'
```

## Ordering Rule for `.claude-plugin/marketplace.json`

Keep `olegvg-skills` first, then concrete groups. The Vercel Skills CLI assigns each skill to the last plugin entry that mentions it, so concrete groups must come after the umbrella to remain visible in the picker.

## Verification

For install-surface changes:

```bash
node -e "const fs=require('fs'); for (const f of ['.claude-plugin/plugin.json','.claude-plugin/marketplace.json','.codex-plugin/plugin.json','.agents/plugins/marketplace.json','skills.sh.json']) JSON.parse(fs.readFileSync(f,'utf8')); console.log('json ok')"
git diff --check
npx skills add ./ --list
```
