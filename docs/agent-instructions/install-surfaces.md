# Install Surfaces

Use this before changing install commands, plugin manifests, marketplace metadata, skills.sh grouping, or README install sections.

## Source of Truth

Runtime skills for the `olegvg-skills` umbrella live under `skills/`. Self-contained standalone plugins live under `plugins/<plugin-name>/` and install into both Claude Code and Codex. Install surfaces are metadata over those source directories:

1. Claude Code plugin marketplace uses `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` for the umbrella and groups, and a nested `plugins/<name>/.claude-plugin/plugin.json` for each standalone plugin; the standalone plugin is a `.claude-plugin/marketplace.json` entry whose `source` points at its plugin root.
2. Vercel Skills CLI reads `SKILL.md` files and `.claude-plugin/marketplace.json` `plugins[].skills` declarations.
3. Codex marketplace uses the root `.codex-plugin/plugin.json` for the umbrella plugin, and a nested `plugins/<name>/.codex-plugin/plugin.json` for each standalone plugin; `.agents/plugins/marketplace.json` indexes both forms.
4. skills.sh website grouping uses `skills.sh.json` only.

## Manifests to Keep in Sync

- `.claude-plugin/plugin.json` describes the Claude Code umbrella plugin.
- `.claude-plugin/marketplace.json` contains concrete install groups plus the umbrella entry, followed by one entry per standalone plugin pointing at `./plugins/<name>`. Root-sourced groups use `strict: false` and explicit `skills` and `commands` arrays; never let a group inherit a sibling group's default command scan.
- `plugins/transcribing-audio/.claude-plugin/plugin.json` describes the standalone plugin for Claude Code; keep its metadata aligned with the sibling `.codex-plugin/plugin.json`.
- `.codex-plugin/plugin.json` describes the Codex umbrella plugin. Do not add unsupported group fields.
- `.agents/plugins/marketplace.json` exposes the Codex umbrella plugin and every standalone plugin in the self-hosted marketplace index.
- `skills.sh.json` mirrors public grouping for the website.

## Claude Code

Claude Code has real plugin install targets from `.claude-plugin/marketplace.json`:

```text
/plugin marketplace add olegvg/olegvg-skills
/plugin install kb-for-agents@olegvg-skills
/plugin install core-dev@olegvg-skills
/plugin install olegvg-skills@olegvg-skills
/plugin install transcribing-audio@olegvg-skills
/reload-plugins
```

`kb-for-agents` installs the KB skills and the namespaced shims `/kb-for-agents:kb-build` through `/kb-for-agents:kb-maintain`. `core-dev` installs portable development skills such as `simplify-code`; it has no command shim. `olegvg-skills` installs every root skill and the same KB shims under `/olegvg-skills:`, but not standalone plugins. `transcribing-audio` installs the standalone audio-transcription plugin with its bundled skill and Python runtime; invoke it as `/transcribing-audio:transcribing-audio` or describe the task normally. It is deliberately outside the umbrella and outside the `skills` arrays so its skill is never installed without the runtime in `plugins/transcribing-audio/`.

## Codex

Codex marketplace packaging contains the umbrella `olegvg-skills` plugin and standalone plugins whose runtimes cannot be represented as a root skill alone. One `.codex-plugin/plugin.json` describes one plugin root.

Install one or both plugins directly from this marketplace:

```bash
codex plugin marketplace add olegvg/olegvg-skills
codex plugin add olegvg-skills@olegvg-skills
codex plugin add transcribing-audio@olegvg-skills
```

Start a new Codex session after installing or updating either plugin. Codex can discover a skill from its description, or the user can invoke `$olegvg-skills:kb-build`, `$olegvg-skills:kb-query`, `$olegvg-skills:simplify-code`, or `$transcribing-audio:transcribing-audio` explicitly. The audio runtime is in `plugins/transcribing-audio/`; it installs as a standalone plugin on Claude Code and Codex. Do not duplicate its skill in the umbrella, the Claude Code groups, or any `plugins[].skills` array — a skill-only install cannot resolve the plugin runtime.

For a group-scoped Codex install, use Vercel Skills CLI with `-a codex`, for example:

```bash
npx skills add olegvg/olegvg-skills --skill simplify-code -a codex
```

## Vercel Skills CLI

Use Vercel Skills CLI in this repository for root skills only. It does not install Claude Code slash commands from `commands/` or the runtime required by standalone plugins such as `transcribing-audio`, whose skill must stay with its runtime under `plugins/<name>/`.

Interactive picker behavior:

- It shows concrete groups such as `Core Dev` and `Kb For Agents`.
- It cannot show the same skill in a concrete group and a visible umbrella group at the same time.
- To install every root skill interactively, select all concrete groups.

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

# Install every root skill non-interactively
npx skills add olegvg/olegvg-skills --skill '*'
```

## Ordering Rule for `.claude-plugin/marketplace.json`

Keep `olegvg-skills` first, then concrete groups. The Vercel Skills CLI assigns each skill to the last plugin entry that mentions it, so concrete groups must come after the umbrella to remain visible in the picker.

## Verification

For install-surface changes:

```bash
node -e "const fs=require('fs'); for (const f of ['.claude-plugin/plugin.json','.claude-plugin/marketplace.json','.codex-plugin/plugin.json','.agents/plugins/marketplace.json','plugins/transcribing-audio/.claude-plugin/plugin.json','plugins/transcribing-audio/.codex-plugin/plugin.json','skills.sh.json']) JSON.parse(fs.readFileSync(f,'utf8')); console.log('json ok')"
git diff --check
npx skills add ./ --list
```
