# OlegVG Skills

[Русская версия](README.ru.md)

Reusable skills for Claude Code, Codex, and other agents supported by the
Vercel Skills CLI. Give a new agent session a map of your project, review a
change against the guarantees it must preserve, and verify mobile behavior on
the intended device. Add the audio plugin when a recording needs a searchable,
speaker-labelled transcript.

## Pick a skill

### KB for Agents

Use `kb-for-agents` when the same project questions keep coming back across
sessions. Build the map once, query it as needed, then use Git changes to keep
the affected parts current and preserve the reasons for shipped decisions.

| Skill | When to use it | What you get |
| --- | --- | --- |
| `kb-build` | An agent or teammate needs to learn a codebase or notes archive. | A local `.kb/` with short indexes, summaries organized by topic, and source references. |
| `kb-query` | You need to find where behavior lives, trace a path, or understand why it was chosen. | A source-backed answer from the relevant summaries and decision records. |
| `kb-check-drift` | Several changes have landed and you want to judge whether the KB is still current. | A report of likely stale topics, broken references, and completed work that may merit a decision record. |
| `kb-refresh` | You know which committed changes affected the KB. | Updated summaries and indexes for the selected paths, with a report and a new refresh watermark by default. |
| `kb-record-decision` | A shipped plan contains a choice future maintainers will need to understand. | One durable record of the decision, alternatives, consequences, and affected topics. |
| `kb-maintain` | You want to review and carry out a maintenance pass from one invocation. | A proposed maintenance plan, batched updates for the approved paths, and a record of what changed. |

Follow the [KB walkthrough](docs/kb-workflow.md) to see all six in one project.
The build uses the [three-layer KB pattern](docs/concept.md). The
[manual templates](templates/README.md) show the files it produces.

### Core Dev

| Skill | When to use it | What you get |
| --- | --- | --- |
| [`deep-code-review`](docs/deep-code-review.md) | You need evidence that a PR preserves a contract or you want a focused audit of an existing module. | Read-only findings with a reachable example, code references, and coverage gaps. Ten methods cover behavior, data, access, states, failures, and rollout. |
| [`simplify-code`](skills/simplify-code/SKILL.md) | A working change duplicates a helper, adds needless branches, or repeats expensive work. | A small, verified cleanup that preserves intended behavior. |
| [`mobile-test-environments`](skills/mobile-test-environments/SKILL.md) | A test depends on an Android emulator, iOS simulator, physical device, or an Appium session. | Inventory, targeted setup and verification, and cleanup scoped to the resources used for the test. |

The `olegvg-skills` umbrella includes both groups. A typical sequence is to
review a risky diff, simplify code while preserving behavior, verify the
mobile flow when it matters, and update the KB after the change lands. The
groups can also be installed and used independently.

### Audio transcription

Install [`transcribing-audio`](plugins/transcribing-audio/skills/transcribing-audio/SKILL.md)
when a meeting, interview, or voice memo needs text you can quote, search, or
subtitle. It transcribes with local or OpenAI ASR, aligns word timestamps to
speakers with local diarization, and can resume an interrupted run. It ships
as a separate Claude Code or Codex plugin with its own runtime.

## Installation

Choose one installation route per host/workspace to avoid duplicate skill copies.
Root skills live under `skills/`; `transcribing-audio` is an independent plugin
with its Python runtime and is outside the umbrella.

### Skills CLI (Bun or Node.js)

Run from the project where you want the skills. Use Bun or Node.js 22.20+
with `npx`. Replace `bunx` with `npx` to run the same examples with Node.js.

```bash
# Inspect remote or local skills without installing.
bunx skills@latest add olegvg/olegvg-skills --list
bunx skills@latest add ./olegvg-skills --list

# Select skills and agents; project scope is the default.
bunx skills@latest add olegvg/olegvg-skills --skill simplify-code --agent codex claude-code

# Install the KB group.
bunx skills@latest add olegvg/olegvg-skills --skill kb-build kb-query kb-refresh kb-check-drift kb-record-decision kb-maintain --agent codex

# Install all root skills into the project, or choose groups interactively.
bunx skills@latest add olegvg/olegvg-skills --skill '*'

# Explicit user-wide install, without prompts.
bunx skills@latest add olegvg/olegvg-skills --skill simplify-code --agent codex --global --yes
```

The picker shows `kb-for-agents` and `core-dev`; select both for the umbrella.
Skills CLI installs the complete skill directory under `.agents/skills/`,
including references and local templates, and links it for agents that use
another skills directory. This route installs portable root skills. Use the
plugin routes below for Claude compatibility shims or the audio runtime.

After a matching release tag is published, pin a source version:

```bash
bunx skills@latest add https://github.com/olegvg/olegvg-skills/tree/v0.10.1 --skill deep-code-review --agent codex

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
codex plugin marketplace add olegvg/olegvg-skills --ref v0.10.1

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
`ffprobe`. Both modes need `HF_TOKEN` for local diarization. OpenAI mode also
needs `OPENAI_API_KEY` and explicit upload consent. Supply the credentials
through `--env-file` or the plugin's dotenv file. The first run can prepare a
cached plugin-local `.venv`. See the [runtime setup](plugins/transcribing-audio/skills/transcribing-audio/references/runtime-and-backends.md).

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
`mobile-test-environments` needs local device access and the relevant CLI tools.
`deep-code-review` needs a coding agent with access to the diff or source
paths being reviewed. Install audio as a full plugin using the routes above.

Every release includes notes, a generated changelog and SHA256SUMS:

```bash
shasum -a 256 -c SHA256SUMS    # macOS; use sha256sum on Linux
```

Local preparation does not publish a tag, release assets or a directory listing.
See [releasing](docs/releasing.md) for reproducible builds and validation.

## Quickstart

### Learn a project and keep the KB current

Open an agent session at the corpus root. With the Claude Code group, build
the KB and ask a question about the project.

~~~text
/kb-for-agents:kb-build .
/kb-for-agents:kb-query Where are refund retries scheduled?
~~~

After committing a change, preview drift and refresh the relevant paths.
When a completed plan captures an important decision, record it by path.

~~~text
/kb-for-agents:kb-check-drift
/kb-for-agents:kb-refresh src/billing/ src/workers/
/kb-for-agents:kb-record-decision planning/refund-retry.md
~~~

Use `/kb-for-agents:kb-maintain` for a guided pass that proposes updates before
applying them. In the Codex umbrella, invoke the equivalent skills as
`$olegvg-skills:kb-build`, `$olegvg-skills:kb-query`, and so on. See the
[KB walkthrough](docs/kb-workflow.md) for inputs, outputs, and examples.

### Review, simplify, or run a mobile check

| Task | What to ask |
| --- | --- |
| Review a retry change | “Use `deep-code-review` to review this PR against main. Check what happens if a worker retries after a provider success.” |
| Clean up a working diff | “Use `simplify-code` on this diff. Keep the behavior and run the focused tests.” |
| Verify a device-dependent flow | “Use `mobile-test-environments` to find the booted Android emulator and verify the form with the software keyboard visible.” |

Use these requests with a skill-only install, or invoke the namespaced skills
in a plugin. For example, use `/core-dev:deep-code-review` in the Claude Code
group or `$olegvg-skills:deep-code-review` in the Codex umbrella. The
[review guide](docs/deep-code-review.md#methods-and-references) explains how
the reviewer chooses and combines its methods.

### Transcribe a recording

After installing the separate audio plugin, invoke
`/transcribing-audio:transcribing-audio /absolute/path/meeting.wav` in Claude Code or
`$transcribing-audio:transcribing-audio /absolute/path/meeting.wav` in Codex.
Choose the ASR mode and speaker policy for the recording.

## Requirements

- An agent with skills support. The installation routes above cover Claude Code,
  Codex, and the hosts supported by Skills CLI.
- For KB skills, a corpus to document. `kb-refresh` and `kb-check-drift`
  require Git history. Build and query also work with a corpus outside Git.

## Privacy and maintenance

Read [PRIVACY.md](PRIVACY.md), [SECURITY.md](SECURITY.md), [CHANGELOG.md](CHANGELOG.md) and the [release guide](docs/releasing.md).

## License

MIT. See [LICENSE](LICENSE).
