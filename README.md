# OlegVG Skills

[Русская версия](README.ru.md)

A grouped personal skill repository for Claude Code, Codex, and agents supported by the Vercel Skills CLI. It ships two installable root-skill groups: `kb-for-agents` for the three-layer knowledge base pattern described in [Knowledge Base for Agents](https://www.linkedin.com/posts/ahaidukof_karpathy-%D1%84%D0%BE%D1%80%D0%BC%D0%B0%D0%BB%D0%B8%D0%B7%D0%BE%D0%B2%D0%B0%D0%BB-%D1%82%D0%BE-%D1%87%D1%82%D0%BE-%D0%BC%D1%8B-%D0%BD%D0%B0%D1%89%D1%83%D0%BF%D0%B0%D0%BB%D0%B8-activity-7446836637143130112-o920/) and `core-dev` for portable development workflows, plus the standalone `transcribing-audio` plugin for Claude Code and Codex.

## What's inside

- **`kb-for-agents` group** — `kb-build`, `kb-query`, `kb-check-drift`, `kb-refresh`, `kb-record-decision`, `kb-maintain`.
- **`core-dev` group** — `simplify-code` for behavior-preserving cleanup, `mobile-test-environments` for Android/iOS devices and Appium sessions, `deep-code-review` for in-depth review of diffs and code paths, including implicit state transitions. Mobile instructions load by platform, with a dependency-free discovery helper. Maestro is optional.
- **`olegvg-skills` umbrella** — all root-skill groups in this repository.
- **`transcribing-audio` plugin (Claude Code and Codex)** — local or OpenAI ASR, speaker diarization, word timestamps, and resumable processing. It is installed separately because it includes its own Python runtime and dependencies.
- **Claude Code commands** — concrete groups expose native skill commands, for example `/kb-for-agents:kb-build`. The umbrella also retains KB compatibility shims in `commands/`; `core-dev` has no shims. Skills CLI installs native skills without those wrappers.
- **Templates** — starter shapes for indexes, summaries, decisions, `_root.md`, state. See [templates/README.md](templates/README.md) for manual-build steps.
- **Docs** — pattern rationale: [concept](docs/concept.md), [navigation rules](docs/navigation-rules.md), [refresh strategy](docs/refresh-strategy.md).

## Installation

Choose one installation route per host/workspace to avoid duplicate skill copies.
Root skills live under `skills/`; `transcribing-audio` is an independent plugin
with its Python runtime and is outside the umbrella.

### Skills CLI (Bun or Node.js)

Run from the project where you want the skills. `install` aliases `add`; every
`bunx skills@latest install` example also works as `npx skills@latest add`.

```bash
# Inspect remote or local skills without installing.
bunx skills@latest install olegvg/olegvg-skills --list
bunx skills@latest install ./olegvg-skills --list

# Select skills and agents; project scope is the default.
bunx skills@latest install olegvg/olegvg-skills --skill simplify-code --agent codex claude-code

# Install the KB group.
bunx skills@latest install olegvg/olegvg-skills --skill kb-build kb-query kb-refresh kb-check-drift kb-record-decision kb-maintain --agent codex

# Install all root skills into the project, or choose groups interactively.
bunx skills@latest install olegvg/olegvg-skills --skill '*'

# Explicit user-wide install, without prompts.
bunx skills@latest install olegvg/olegvg-skills --skill simplify-code --agent codex --global --yes
```

The picker shows `kb-for-agents` and `core-dev`; select both for the umbrella.
These installs copy complete skill directories including references and local
templates. They do not install `commands/` shims or the audio runtime. The audio
skill is hidden from generic discovery because it cannot run alone.

After a matching release tag is published, pin a source version:

```bash
bunx skills@latest install https://github.com/olegvg/olegvg-skills/tree/v0.10.0 --skill deep-code-review --agent codex

# Update selected project installations to available upstream changes.
bunx skills@latest update simplify-code --project
```

Use the pinned source again when intentionally retaining an exact version. See
[Skills CLI](https://github.com/vercel-labs/skills) for agents and update scopes.

### Claude Code marketplace and local loading

```bash
claude plugin marketplace add olegvg/olegvg-skills --scope project
claude plugin install kb-for-agents@olegvg-skills --scope project
claude plugin install core-dev@olegvg-skills --scope project
# Alternatively, install the umbrella instead of its individual groups.
claude plugin install olegvg-skills@olegvg-skills --scope project
# Independent runtime plugin, installed separately.
claude plugin install transcribing-audio@olegvg-skills --scope project

claude plugin marketplace update olegvg-skills
claude plugin update olegvg-skills@olegvg-skills --scope project
claude plugin update transcribing-audio@olegvg-skills --scope project
```

Update the specific group you installed when using individual groups, then restart
Claude Code or run `/reload-plugins`. Interactive equivalents are
`/plugin marketplace add olegvg/olegvg-skills` and
`/plugin install <group>@olegvg-skills`.

Test a checkout without installing it:

```bash
claude --plugin-dir ./olegvg-skills
claude --plugin-dir ./olegvg-skills/plugins/transcribing-audio
```

KB commands use `/kb-for-agents:kb-build` or `/olegvg-skills:kb-build`;
`core-dev` has no command shims. Concrete groups load native skills; the
umbrella retains the legacy KB shims. Audio uses
`/transcribing-audio:transcribing-audio /absolute/path/meeting.wav`.
See [Claude plugins](https://code.claude.com/docs/en/plugins).

### Codex marketplace (remote, local or pinned)

```bash
codex plugin marketplace add olegvg/olegvg-skills
codex plugin add olegvg-skills@olegvg-skills
codex plugin add transcribing-audio@olegvg-skills

# For a prepared local checkout, use this source instead of the remote one.
codex plugin marketplace add ./olegvg-skills

# Or pin an existing published release tag on the remote marketplace.
codex plugin marketplace add olegvg/olegvg-skills --ref v0.10.0

# Refresh the configured marketplace and installed plugin caches.
codex plugin marketplace upgrade olegvg-skills
```

Choose one marketplace source. `marketplace upgrade` applies to Git sources;
for a local checkout, pull/edit that checkout and reinstall the plugin with
`codex plugin add` to refresh its cache. Start a new session after installation/refresh.
Invoke `$olegvg-skills:kb-build`, `$olegvg-skills:kb-query`,
`$olegvg-skills:simplify-code` or `$transcribing-audio:transcribing-audio`.
For group-scoped Codex installs, use the Skills CLI with `--agent codex`.
See the [official packaging guide](https://developers.openai.com/plugins/build/plugins).

### Runtime requirements for transcribing-audio

The separate audio plugin needs macOS or Linux, Python 3.13, `uv`, `ffmpeg` and
`ffprobe`. Local diarization needs approved Hugging Face access via `HF_TOKEN`.
Its first run prepares a cached plugin-local `.venv`. Audio stays local by
default; OpenAI ASR requires explicit consent before any chunk is uploaded.
The root instruction skills do not need these dependencies.

### ZIPs and Claude Desktop

Download artifacts from [Releases](https://github.com/olegvg/olegvg-skills/releases)
when the matching release has been published. A full
`olegvg-skills-plugin-<version>.zip` includes the manifests, root skills,
commands, docs and independent audio runtime. Extract it and use the local
marketplace or `--plugin-dir` route above. Portable root `plugin.json` declares
Agent Plugins 1.0.0; Codex/Claude manifests provide host compatibility.

Individual `<skill>-<version>.zip` archives contain SKILL.md, every reference,
local templates/metadata and LICENSE. Upload these five through the desktop skill UI:
`kb-build`, `kb-query`, `kb-refresh`, `kb-check-drift`, `simplify-code`.
`kb-record-decision` and `kb-maintain` archives target coding-agent hosts with
the required plan/orchestration capabilities and companion skills.
`mobile-test-environments` requires a host with local device/CLI access and separately installed SDKs/drivers. Audio is
available only with its full plugin runtime, never as a skill-only ZIP.

Every release includes notes, a generated changelog and SHA256SUMS:

```bash
shasum -a 256 -c SHA256SUMS    # macOS; use sha256sum on Linux
```

Local preparation does not publish a tag, release assets or a directory listing.
See [releasing](docs/releasing.md) for reproducible builds and validation.

## Quickstart

After installing `kb-for-agents` in Claude Code and running `/reload-plugins`, use the native KB skill commands in a session opened at your corpus root:

```
/kb-for-agents:kb-build .
/kb-for-agents:kb-query where are fees charged?
```

After you've made changes to the corpus:

```
/kb-for-agents:kb-check-drift
/kb-for-agents:kb-refresh src/billing/
```

When a planned piece of work ships and you want its key choices preserved:

```
/kb-for-agents:kb-record-decision docs/plans/2026-03-19-1400/plan-billing-rewrite.md
```

After installing the Codex umbrella plugin, start a new session and use the equivalent skills:

```
$olegvg-skills:kb-build .
$olegvg-skills:kb-query where are fees charged?
$transcribing-audio:transcribing-audio /absolute/path/meeting.wav
```

For local mobile-environment work, invoke `$mobile-test-environments` (or
`/core-dev:mobile-test-environments` in the Claude group), for example:
“Show available Android emulators and virtual iPhones without interrupting running tests.”
The installed SDKs/drivers remain external prerequisites; the skill does not install them automatically.

Invoke `$deep-code-review` after a skill-only install,
`$olegvg-skills:deep-code-review` in the Codex plugin, or
`/core-dev:deep-code-review` in the Claude Code group. Specify a diff, PR,
working tree, or code path and the behavior you want reviewed. See the
[review rationale](docs/deep-code-review.md).

To audit implicit state machines, open the session at the application root
and ask `deep-code-review` to audit state transitions in the module you want to
review. The [lifecycle audit guide](skills/deep-code-review/references/lifecycles.md)
carries forward the workflow from `audit-state-machines` as of v0.10.0.

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

## Privacy and maintenance

Read [PRIVACY.md](PRIVACY.md), [SECURITY.md](SECURITY.md), [CHANGELOG.md](CHANGELOG.md) and the [release guide](docs/releasing.md).

## License

MIT. See [LICENSE](LICENSE).
