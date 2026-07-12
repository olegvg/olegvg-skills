# Transcribing Audio Plugin Stage 5: Documentation and Validation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finalize the plugin manifest, embedded progressive-disclosure skill, marketplace/install lifecycle, and interface metadata; prove offline script-runtime quality and coverage; then smoke-test and forward-test the installed plugin in fresh agent contexts.

**Architecture:** `.codex-plugin/plugin.json` is the package contract, `skills/transcribing-audio/SKILL.md` is the agent entry point, and plugin-root `scripts/` is the only executable implementation. `SKILL.md` contains trigger metadata, privacy rules, the short operational workflow, stop conditions, portable script invocation, and a one-level reference routing table. Automated validation separately covers plugin ingestion, marketplace metadata, embedded-skill structure, runtime correctness, type/lint/security gates, and acceptance criteria; fresh agents validate discovery only after installation.

**Tech Stack:** Codex plugin and skill formats, plugin-creator and skill-creator scripts, JSON/Markdown/YAML, pytest/coverage, pyright, ruff, optional MLX/CUDA/OpenAI/pyannote smoke environments, fresh subagents.

**Prerequisite:** Execute only after the [Stage 4 plan](plan-transcribing-audio-plugin-stage-4-cli-integration.md) is complete and the [Stage 4 checklist](checklist-transcribing-audio-plugin-stage-4-cli-integration.md) is approved.

## Global Constraints

- Complete and approve Stages 1–4 first.
- Preserve the Stage 1 scaffolded plugin name/version/author contract and keep outer folder, manifest, embedded skill, and marketplace entry aligned.
- Keep apps, MCP servers, hooks and assets out of the manifest unless those components actually exist; version 1 plans none of them.
- `SKILL.md` frontmatter contains only `name` and `description`.
- Put every trigger phrase/context in `description` because the body loads only after trigger.
- Keep `SKILL.md` below 500 lines and concise enough to load routinely.
- Use imperative/infinitive instructions.
- Keep references one level below `SKILL.md`; do not create nested reference chains.
- Do not duplicate detailed thresholds, schemas, provider fields, or backend setup between `SKILL.md` and references.
- Do not create README, installation guide, quick reference, changelog, or committed audio.
- Generate `agents/openai.yaml` deterministically and quote all string values.
- Default verification must be offline and model-download-free.
- Forward-test with minimal task-local context; do not give evaluators the intended answer or known failure diagnosis.
- Do not close acceptance without one successful fresh-agent scenario and the required 80% coverage.
- Forward-test the installed marketplace plugin in a new thread; source-tree presence is not discovery evidence.

---

### Task 1: Write the concise skill entry point and routing table

**Files:**
- Modify: `plugins/transcribing-audio/skills/transcribing-audio/SKILL.md`
- Create: `plugins/transcribing-audio/tests/test_skill_contract.py`

**Interfaces:**
- Consumes: completed CLI behavior and six planned references.
- Produces: natural-language discovery and an unambiguous, privacy-preserving agent workflow.

- [ ] **Step 1: Write failing metadata/content tests**

Parse the frontmatter and assert:

- exact `name: transcribing-audio`;
- only `name` and `description` keys;
- description mentions transcription, diarization/speaker labels, voice memos/meetings/interviews, local and OpenAI modes, and timestamps;
- every reference link exists and is one directory below `SKILL.md`;
- body is below 500 lines;
- body contains local/OpenAI choice, upload consent, resume, stop-on-quality-failure, canonical JSON-first output, and all common command flags;
- body does not contain secret examples, package installation commands, quality threshold tables, full JSON schema, or copied provider API documentation.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
uv run --project plugins/transcribing-audio pytest plugins/transcribing-audio/tests/test_skill_contract.py -q
```

Expected: FAIL because `SKILL.md` is still the scaffold.

- [ ] **Step 3: Write exact frontmatter**

Use:

```yaml
---
name: transcribing-audio
description: Transcribe audio recordings into word-timestamped, speaker-labelled JSON and readable text with local or OpenAI ASR plus local diarization. Use for voice memos, meetings, interviews, calls, multi-speaker recordings, transcription requests, diarization requests, speaker labels, subtitles, resumable audio processing, or suspected ASR repetition and hallucination loops.
---
```

- [ ] **Step 4: Write only the core operational body**

Use these sections:

```text
# Transcribing Audio
## Safety and privacy
## Choose the mode
## Run the pipeline
## Stop conditions
## Common commands
## Read references only when needed
```

Core workflow must tell the agent to:

1. resolve the input/output paths without copying audio into the repository;
2. run the skill launcher and let every TTY run ask local/OpenAI;
3. never infer upload permission and describe OpenAI upload before confirmation;
4. choose exact/range/automatic speaker flags from user intent;
5. use `--resume` after interruption;
6. stop and report exact intervals when quality retry remains unresolved;
7. treat canonical JSON as authoritative and TXT/SRT/VTT as derivatives;
8. never print dotenv values or commit audio/runtime state.

Common commands include local interactive, explicit non-interactive local, explicit non-interactive OpenAI with consent, exact/range speaker examples, resume, reprobe, overwrite, SRT and VTT. The skill must resolve its own absolute directory and invoke `../../scripts/transcribe_audio.py` from there; it must never assume repository cwd or hardcode the source checkout path. Contract tests execute the documented resolver against both a checkout-shaped fixture and a relocated installed-plugin fixture.

- [ ] **Step 5: Add the routing table**

| Need | Read |
| --- | --- |
| runtime fingerprint, probe, cached venv, backend fallback, reprobe | `references/runtime-and-backends.md` |
| MLX/faster-whisper models, language and independent windows | `references/local-asr.md` |
| OpenAI model capability, upload consent, chunks and API errors | `references/openai-asr.md` |
| pyannote speaker counts, raw labels, alignment and names | `references/diarization-and-alignment.md` |
| gate definitions, thresholds, retries and unresolved failures | `references/quality-and-recovery.md` |
| canonical JSON, TXT/SRT/VTT fields and validation | `references/output-schema.md` |

State explicitly: read only the rows needed for the current request.

- [ ] **Step 6: Verify GREEN and commit**

Run skill-contract tests. Commit with `git commit -m "docs: define audio transcription skill workflow"`.

---

### Task 2: Write non-duplicative one-level references

**Files:**
- Create: `plugins/transcribing-audio/skills/transcribing-audio/references/runtime-and-backends.md`
- Create: `plugins/transcribing-audio/skills/transcribing-audio/references/local-asr.md`
- Create: `plugins/transcribing-audio/skills/transcribing-audio/references/openai-asr.md`
- Create: `plugins/transcribing-audio/skills/transcribing-audio/references/diarization-and-alignment.md`
- Create: `plugins/transcribing-audio/skills/transcribing-audio/references/quality-and-recovery.md`
- Create: `plugins/transcribing-audio/skills/transcribing-audio/references/output-schema.md`
- Modify: `plugins/transcribing-audio/tests/test_skill_contract.py`

**Interfaces:**
- Consumes: implemented constants/interfaces and current primary documentation.
- Produces: detailed knowledge loaded only for relevant tasks.

- [ ] **Step 1: Write failing reference-consistency tests**

Create one machine-readable `constants.py` module for model IDs/revisions, CLI flag names/defaults, quality-policy values, JSON/runtime schema versions, stage names and output suffixes. Assert executable modules, `SKILL.md` command examples, and references match those constants; do not require textual uniqueness because a flag may be mentioned in both the concise workflow and one relevant reference. Test links from `SKILL.md`; references do not link to a second reference as a required next step.

- [ ] **Step 2: Write `runtime-and-backends.md`**

Document supported macOS/Linux matrix, external prerequisites, `/tmp` layout, base/runtime fingerprints, cheap index, MLX→CUDA→CPU choice, separate pyannote compute device, cache/reprobe triggers, `0700`/locking, persistent model caches, and safe recovery commands. Do not repeat the general mode prompt.

- [ ] **Step 3: Write `local-asr.md`**

Document approved MLX/faster models and versions, mandatory word timestamps, `condition_on_previous_text=false`, chunk/overlap behavior, language auto-detection/pinning, device compute types, model-cache locations, and opt-in local model smoke commands. Link to primary MLX/faster docs.

- [ ] **Step 4: Write `openai-asr.md`**

Recheck `openai-docs` and record the current selected model, timestamp-capable request/response shape, conservative byte limit, supported audio format, retry behavior, required `OPENAI_API_KEY`, consent rules, redacted error categories and opt-in network smoke command. State that cloud diarization is not used. Do not include a literal token.

- [ ] **Step 5: Write `diarization-and-alignment.md`**

Document approved pyannote model/revision, `HF_TOKEN`/gated-model prerequisite, local device behavior, exact/range/automatic kwargs, exact-label validation, maximum-overlap/tie/nearest rules, 1.5-second turn merge, post-alignment name mapping, and no biometric profiles.

- [ ] **Step 6: Write `quality-and-recovery.md`**

Copy `QualityPolicy(version="1")` constants from code into the single authoritative table, explain every issue code/severity, one-result-per-planned-chunk coverage plus measured/backend silence evidence, one retry with smaller independent chunks, and failure report semantics. Add the Russian repetition fixture rationale without copying user audio.

- [ ] **Step 7: Write `output-schema.md`**

Document schema version 1 with a compact complete JSON example containing synthetic text, mandatory word timestamps, nullable confidence, raw/display speakers, model/stage/retry provenance, quality status/warnings, default filenames, exact TXT format and SRT/VTT rules. Do not duplicate full construction algorithms.

- [ ] **Step 8: Verify reference consistency and commit**

Run `test_skill_contract.py` and commit with `git commit -m "docs: add transcription skill references"`.

---

### Task 3: Finalize and validate plugin, embedded-skill, and marketplace contracts

**Files:**
- Modify: `plugins/transcribing-audio/.codex-plugin/plugin.json`
- Modify: `plugins/transcribing-audio/skills/transcribing-audio/agents/openai.yaml`
- Modify: `plugins/transcribing-audio/tests/test_skill_contract.py`
- Create: `plugins/transcribing-audio/tests/test_plugin_contract.py`
- Modify only through scaffold/update helpers when required: `.agents/plugins/marketplace.json`

**Interfaces:**
- Consumes: Stage 1 plugin scaffold and finalized `SKILL.md`.
- Produces: a validator-clean plugin manifest, deterministic skill metadata, and a coherent repo marketplace entry.

- [ ] **Step 1: Finalize the plugin manifest and write failing contract tests**

Keep real scaffolded values for required metadata and set only supported fields. Assert strict semver, required author name, `skills: "./skills/"`, and coherent interface metadata for Audio Transcription. Assert that folder/manifest/skill/marketplace names match and that manifest paths remain relative with `./`. Assert `apps`, `mcpServers`, `hooks`, icon/logo/screenshots and other absent components are not declared. Do not leave TODO placeholders.

Test the marketplace entry has local source `./plugins/transcribing-audio`, `AVAILABLE` installation, `ON_INSTALL` authentication and a non-empty category; preserve existing marketplace display metadata and entry order.

- [ ] **Step 2: Regenerate embedded-skill metadata**

Run:

```bash
uv run --isolated --no-project --with pyyaml "$HOME/.codex/skills/.system/skill-creator/scripts/generate_openai_yaml.py" \
  plugins/transcribing-audio/skills/transcribing-audio \
  --interface display_name="Audio Transcription" \
  --interface short_description="Transcribe and diarize speaker-labelled audio" \
  --interface default_prompt='Use $transcribing-audio to transcribe this recording with speaker labels.'
```

Expected:

```yaml
interface:
  display_name: "Audio Transcription"
  short_description: "Transcribe and diarize speaker-labelled audio"
  default_prompt: "Use $transcribing-audio to transcribe this recording with speaker labels."
```

Keep plugin `interface` metadata and embedded-skill `agents/openai.yaml` semantically consistent while respecting their different schemas. Do not invent icons, brand color, MCP dependencies, or unsupported fields.

- [ ] **Step 3: Test metadata constraints**

Assert all strings are quoted when serialized, short description is 25–64 characters, default prompt mentions `$transcribing-audio`, and metadata matches `SKILL.md`.

- [ ] **Step 4: Run both validators and commit**

Run:

```bash
uv run --isolated --no-project --with pyyaml "$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py" \
  plugins/transcribing-audio/skills/transcribing-audio
python3 "$HOME/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py" \
  plugins/transcribing-audio
```

Expected: embedded-skill and plugin validation both pass. Commit with `git commit -m "chore: finalize transcription plugin metadata"`.

---

### Task 4: Reach offline quality, typing, lint and security gates

**Files:**
- Modify as required: `plugins/transcribing-audio/scripts/audio_transcriber/*.py`
- Modify as required: `plugins/transcribing-audio/tests/*.py`
- Modify during execution: `checklist-transcribing-audio-plugin-stage-5-validation.md`

**Interfaces:**
- Consumes: full default suite.
- Produces: ≥80% branch-aware executable coverage and clean static/security review.

- [ ] **Step 1: Run full offline suite and coverage**

Run:

```bash
export PLUGIN_ROOT="$PWD/plugins/transcribing-audio"
export UV_PROJECT_ENVIRONMENT="$PLUGIN_ROOT/.venv"
uv sync --project "$PLUGIN_ROOT" --frozen --all-extras --group dev
uv run --project "$PLUGIN_ROOT" pytest "$PLUGIN_ROOT/tests" -m "not network and not models and not smoke" -q
uv run --project "$PLUGIN_ROOT" pytest "$PLUGIN_ROOT/tests" \
  -m "not network and not models and not smoke" \
  --cov="$PLUGIN_ROOT/scripts/audio_transcriber" \
  --cov-branch \
  --cov-report=term-missing \
  --cov-fail-under=80
```

Expected: PASS and total coverage at least 80%. Add focused behavioral tests for uncovered error branches; do not use blanket pragmas or exclude files to inflate coverage.

- [ ] **Step 2: Run type/lint/format gates**

Run:

```bash
uv run --project "$PLUGIN_ROOT" pyright --project "$PLUGIN_ROOT/pyproject.toml"
uvx ruff check "$PLUGIN_ROOT"
uvx ruff format --check "$PLUGIN_ROOT"
git diff --check
```

Expected: PASS.

- [ ] **Step 3: Run security review**

Inspect the complete diff for hardcoded secrets, unsafe dotenv merging, `shell=True`, user-controlled path traversal, symlink attacks, world-readable `/tmp` content, unbounded subprocess/provider errors, missing consent, output overwrite bypass, secrets in fingerprints/manifests, and unsafe deserialization. Search only for suspicious key names/patterns, never print real dotenv contents.

Run dependency vulnerability audit with the project-approved Python audit tool if available. If installing a new audit tool would change the skill, use an ephemeral `uvx` invocation and record its version/output in the checklist.

- [ ] **Step 4: Simplify and rerun gates**

Consolidate duplicated atomic JSON, timestamp, redaction, and validation behavior without merging unrelated modules. Rerun all Task 4 commands after the final edit. Commit with `git commit -m "test: complete transcription runtime quality gates"`.

---

### Task 5: Install the repo-local plugin and prove the update lifecycle

**Files:**
- Modify during execution: `checklist-transcribing-audio-plugin-stage-5-validation.md`
- Do not hand-edit marketplace files during reinstall iterations.

**Interfaces:**
- Consumes: validator-clean plugin source and `.agents/plugins/marketplace.json`.
- Produces: an installed plugin visible to Codex plus recorded reinstall/new-thread evidence.

- [ ] **Step 1: Register the explicit repo marketplace when necessary**

Check current CLI syntax and configured plugins first:

```bash
codex plugin marketplace add --help
codex plugin list
```

If this repo marketplace is not configured, add the repository root that owns `.agents/plugins/marketplace.json` using the currently documented `codex plugin marketplace add <path-to-marketplace-root>` form. Do not add the default personal marketplace and do not replace another configured marketplace with the same name.

- [ ] **Step 2: Read the marketplace name and install the plugin**

```bash
python3 "$HOME/.codex/skills/.system/plugin-creator/scripts/read_marketplace_name.py" \
  --marketplace-path "$PWD/.agents/plugins/marketplace.json"
codex plugin add "transcribing-audio@<printed-marketplace-name>"
codex plugin list
```

Expected: Codex lists `transcribing-audio` from the intended local marketplace and installed content includes `.codex-plugin/plugin.json`, the embedded skill, and executable `scripts/transcribe_audio.py`.

- [ ] **Step 3: Prove the supported update/reinstall path**

After any plugin change made during this stage, never edit marketplace/config files merely to defeat caching. Run:

```bash
python3 "$HOME/.codex/skills/.system/plugin-creator/scripts/update_plugin_cachebuster.py" \
  plugins/transcribing-audio
python3 "$HOME/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py" \
  plugins/transcribing-audio
codex plugin add "transcribing-audio@<printed-marketplace-name>"
```

Assert that the helper preserves the base version and replaces a single `+codex.<cachebuster>` suffix. Start a new thread so Codex loads the updated skill and scripts. Record the installed version and new-thread pickup evidence in the checklist.

---

### Task 6: Run opt-in smoke tests and installed-plugin forward tests

**Files:**
- Modify during execution: `checklist-transcribing-audio-plugin-stage-5-validation.md`
- No committed audio or generated forward-test output.

**Interfaces:**
- Consumes: optional `TRANSCRIBER_SMOKE_AUDIO`, `TRANSCRIBER_SMOKE_SPEAKERS`, local model access, optional OpenAI permission.
- Produces: acceptance evidence from realistic execution and fresh agent behavior.

- [ ] **Step 1: Run local hardware/model smoke when available**

With a user-provided recording outside the repository:

```bash
export TRANSCRIBER_SMOKE_AUDIO="/absolute/private/path/to/recording"
plugins/transcribing-audio/scripts/transcribe_audio.py "$TRANSCRIBER_SMOKE_AUDIO" \
  --mode local \
  --speakers "$TRANSCRIBER_SMOKE_SPEAKERS" \
  --resume
```

On a TTY, still answer the mode prompt. Verify backend/device provenance, exact distinct raw labels, mandatory word timestamps, and no repetition loop. Do not copy the recording or final output into git.

- [ ] **Step 2: Run optional OpenAI smoke only with explicit approval**

Use a short non-sensitive recording and explicit upload consent. Confirm chunks remain below the documented limit, OpenAI supplies word timestamps, pyannote remains local, and no key appears in output. Skip and record `not authorized` rather than infer permission.

- [ ] **Step 3: Forward-test natural discovery in a fresh agent**

After installation/reinstallation, start a new thread where the plugin is loaded, but do not name or point to the plugin or embedded skill. Reuse the exact `TRANSCRIBER_FORWARD_AUDIO` and `TRANSCRIBER_FORWARD_SPEAKERS` from the Stage 1 RED baseline and give it only:

```text
Transcribe <TRANSCRIBER_FORWARD_AUDIO> locally into word-timestamped JSON and speaker-labelled text for exactly <TRANSCRIBER_FORWARD_SPEAKERS> speakers. Make interrupted work resumable.
```

Expand variables to actual values before dispatch. Do not provide the design, plugin/skill name or path, expected commands, suspected bugs, or previous output. Verify the agent discovers the embedded `transcribing-audio` skill through the installed plugin, resolves the launcher from the installed skill location, reads only necessary references, prompts for mode on TTY, keeps audio local, uses exact speaker flags, produces valid artifacts, and recommends `--resume` after interruption. Compare emitted commands and artifacts directly with the Stage 1 baseline.

- [ ] **Step 4: Forward-test cloud refusal and hallucination handling**

In separate fresh contexts:

```text
Transcribe <absolute non-sensitive smoke audio path> with OpenAI and speaker labels.
```

Verify upload never begins before explicit confirmation. The deterministic Russian JSON fixture and Stage 4 integration test are the required repetition-recovery evidence. Optionally, when the user provides `TRANSCRIBER_HALLUCINATION_AUDIO` for a recording that previously exhibited the loop, run it through the normal skill interface—never a hidden public-CLI test hook—and verify the loop is avoided or reported with exact failed intervals after one retry. Record `not provided` when this optional artifact is unavailable; do not block the required forward-test scenario.

- [ ] **Step 5: Compare against RED baseline and refine only observed gaps**

Compare the fresh-agent behavior with Stage 1 baseline omissions. Change `SKILL.md`, a reference, or plugin metadata only for observed transferable gaps, not to encode the exact test answer. After any change, rerun plugin/skill validators, offline suite, coverage, pyright and ruff, then use the cachebuster/reinstall/new-thread flow again. Commit with `git commit -m "test: forward-test audio transcription plugin"`.

---

### Task 7: Run repository regression gates and acceptance trace

**Files:**
- Modify during execution: `checklist-transcribing-audio-plugin-stage-5-validation.md`

**Interfaces:**
- Consumes: final plugin diff and source specification.
- Produces: evidence that the isolated plugin did not affect `psy_bot` and every acceptance criterion is covered.

- [ ] **Step 1: Run repository gates**

Run:

```bash
make test
uv run pyright
uvx ruff check plugins/transcribing-audio
git diff --check
```

Expected: PASS. If a pre-existing unrelated repository failure exists, record the exact command/output and prove the plugin-focused gates pass; do not modify project logic to mask it.

- [ ] **Step 2: Walk acceptance criteria**

Map evidence:

| Acceptance criterion | Evidence |
| --- | --- |
| Natural transcription/diarization/voice memo/meeting discovery | frontmatter tests + fresh-agent forward test |
| First launch provisions; later launch skips probe | bootstrap cache tests + smoke logs |
| Deterministic MLX/CUDA/CPU recovery | probe matrix tests |
| Every interactive run asks mode | CLI TTY matrix |
| OpenAI dotenv key and confirmation | config/consent/integration tests |
| Exact/ranged/automatic speakers | config + pyannote adapter tests |
| Word timestamps aligned to raw labels | ASR/alignment/integration artifacts |
| Repetition retry blocks bad final | Russian fixture + integration/forward test |
| Interrupted run resumes by stage | state/pipeline interruption tests |
| Final JSON/TXT structurally valid | renderer/integration tests |
| Runtime coverage at least 80% | coverage report |
| Quick validation and forward test pass | recorded commands/artifacts |
| Valid plugin package and coherent normalized names | plugin contract tests + `validate_plugin.py` |
| Repo marketplace entry is valid and preserved | marketplace contract tests + install log |
| Installed scripts are present and location-portable | installed-layout test + relocated launcher-resolution test |
| Install/reinstall is picked up in a new thread | cachebuster/reinstall log + fresh-thread discovery |

- [ ] **Step 3: Final review and commit**

Run correctness and security review over the full plugin, address every CRITICAL/HIGH finding, rerun affected gates, complete the Stage 5 checklist, and create one coherent final commit only for remaining plan/checklist evidence.

---

## Stage 5 Completion Gate

Run the complete Task 3–7 command set after the final edit. The plugin is complete only when:

- plugin validation and embedded-skill quick validation pass;
- marketplace install, cachebuster reinstall and new-thread pickup are proven;
- offline pytest/coverage/pyright/ruff pass;
- coverage is at least 80%;
- repository regressions are clear;
- one realistic fresh-agent local forward test passes;
- cloud consent refusal is proven;
- exact speaker labels and repetition protection are observed;
- every acceptance row has concrete evidence;
- no credentials, audio, `/tmp` state, model cache, or transcript output is committed.

Run `/simplify`, then walk and complete [the Stage 5 checklist](checklist-transcribing-audio-plugin-stage-5-validation.md). Review the final diff before branch integration.
