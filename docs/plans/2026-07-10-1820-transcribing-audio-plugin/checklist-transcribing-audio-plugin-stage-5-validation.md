# Transcribing Audio Plugin Stage 5 Verification Checklist

## Deliverable Summary

Stage 5 finalizes the plugin manifest, embedded trigger-rich skill, six progressive-disclosure references, marketplace/install lifecycle, deterministic UI metadata, offline quality/static/security gates, opt-in backend/provider smoke tests, installed-plugin forward tests and complete acceptance evidence.

## Plugin and Embedded Skill Contracts

- [x] `.codex-plugin/plugin.json` passes `validate_plugin.py` with strict semver and no TODO placeholders.
- [x] Folder, manifest, embedded skill and marketplace entry names all match `transcribing-audio`.
- [x] Manifest declares `./skills/` and no absent app, MCP, hook, icon, logo, screenshot or asset component.
- [x] Marketplace source/policies/category are valid and unrelated entries/order remain unchanged.
- [x] Frontmatter contains only `name` and comprehensive `description`.
- [x] Natural requests for transcription, diarization, voice memos, meetings, interviews, speaker labels, timestamps and subtitles trigger the skill.
- [x] `SKILL.md` is under 500 lines and contains only core workflow/safety/commands/routing.
- [x] Six one-level references exist and are linked directly.
- [x] Detailed workflow facts live in one of the six direct references; `SKILL.md` retains only routing and operating rules.
- [x] No README/install guide/quick reference/changelog exists.
- [x] `agents/openai.yaml` matches the finalized skill and has no invented optional fields.
- [x] Nested-skill `quick_validate.py` passes.
- [x] Documented launcher resolution works from a relocated installed-plugin path without repository cwd.

## Install and Update Lifecycle

- [ ] The explicit repo marketplace is configured without replacing an unrelated marketplace. Blocked: Codex user-configuration write was denied by the platform usage limit.
- [ ] `transcribing-audio@<marketplace-name>` installs and appears in `codex plugin list`. Blocked by marketplace registration.
- [ ] Installed content contains the embedded skill and executable runtime scripts. Blocked by marketplace registration.
- [x] `update_plugin_cachebuster.py` preserves the `0.1.0` base version and leaves one cachebuster suffix (`0.1.0+codex.20260711221133`).
- [ ] Reinstall succeeds without hand-editing marketplace/config files. Blocked by marketplace registration.
- [ ] A new thread discovers the updated embedded skill through the installed plugin. Not run: the user explicitly prohibited subagents and installation was blocked.

## Runtime Quality and Security

- [x] Offline default pytest passes without network/model downloads (125 passed).
- [x] Branch-aware executable coverage is at least 80% (80.39%).
- [x] Pyright strict passes (0 errors, 0 warnings).
- [x] Ruff check and format pass.
- [ ] Dependency/security vulnerability result is not available. Local `pip-audit --dry-run` collected 122 installed packages without contacting an audit service. The full lookup remained prohibited by the platform's external-data-disclosure policy even after explicit user approval.
- [x] No hardcoded or emitted secrets exist in the reviewed plugin source or documentation.
- [x] No unsafe shell, path, symlink, permission, overwrite or deserialization issue remains in the reviewed plugin source.
- [x] Manual correctness/security review found no CRITICAL/HIGH issue.

## Smoke and Forward Tests

- [ ] Local smoke uses an external non-committed recording. Not run: no recording was provided.
- [ ] Actual backend/device/model provenance is correct. Requires the unavailable local smoke.
- [x] Exact mode returns the requested distinct raw-label count in deterministic diarization tests.
- [x] Canonical words have timestamps and speaker alignment in ASR, alignment, renderer, and pipeline integration tests.
- [x] Known repetition is avoided or blocked after one retry by the deterministic quality fixture.
- [x] Deterministic fixture/integration proves repetition recovery; external hallucination recording: `not provided`.
- [x] OpenAI smoke: `not authorized`; no upload was attempted.
- [ ] Fresh agent receives a natural request without plugin/skill name or path and discovers the installed plugin's skill. A fresh blind test was run after the user authorized it, but—because marketplace installation is intentionally excluded—it did not discover the source-tree skill and proposed a different stack. This is not acceptance evidence.
- [ ] GREEN forward test reuses the exact external recording/count and compares commands/artifacts with Stage 1 RED baseline. No Stage 1 external recording was available.
- [ ] Fresh agent reads only necessary references and follows mode/privacy/resume workflow. Excluded by the user's no-subagents instruction.
- [x] Separate fresh-agent cloud request never uploads before consent. A blind fresh-context request stopped before upload and requested explicit OpenAI authorization plus an API key. This proves refusal behavior only; it is not installed-plugin discovery evidence.
- [x] No audio, transcript, model cache, or runtime state is tracked by Git; generated test artifacts remain under temporary directories.

## Acceptance Trace

- [x] Plugin manifest/name/component evidence: `test_plugin_contract.py`, `test_layout.py`, and official validator.
- [ ] Marketplace preservation/install evidence: source entry is contract-tested; installation is intentionally excluded for this run.
- [ ] Portable installed-script evidence: checkout and relocated-layout resolver test passes; an installed package could not be inspected.
- [ ] Cachebuster/reinstall/new-thread evidence: cachebuster verified; reinstall is intentionally excluded and the blind fresh-context test failed discovery without it.
- [ ] Discoverability evidence: frontmatter contract passes; installed fresh-agent discovery remains unavailable because installation is intentionally excluded.
- [x] First/subsequent launch evidence: bootstrap cache tests.
- [x] Backend selection/recovery evidence: bootstrap probe/recovery tests.
- [x] Interactive mode evidence: CLI TTY matrix tests.
- [x] OpenAI key/consent evidence: config, ASR, CLI, and pipeline tests.
- [x] Speaker-count evidence: model and diarization tests.
- [x] Timestamp/alignment evidence: ASR, alignment, renderer, and integration tests.
- [x] Repetition recovery evidence: Russian fixture and quality/pipeline tests.
- [x] Resume evidence: state and pipeline integration tests.
- [x] JSON/TXT validation evidence: renderer and pipeline integration tests.
- [x] Coverage evidence: 80.39% branch-aware report.
- [ ] Quick-validation/forward-test evidence: validator passes; blind fresh-context local discovery did not pass without the intentionally excluded installation prerequisite.

## Command Evidence

```text
quick_validate: PASS — official `quick_validate.py`.
plugin validator: PASS — official `validate_plugin.py` via isolated PyYAML environment.
marketplace registration: BLOCKED — platform usage limit denied the user-configuration write.
plugin install/list: NOT RUN — marketplace registration blocked.
cachebuster/reinstall: cachebuster PASS (`0.1.0+codex.20260711221133`); reinstall BLOCKED.
new-thread pickup: NOT RUN — user explicitly prohibited subagents; marketplace installation blocked.
offline pytest: PASS — 125 passed, no network/model/smoke marker.
coverage: PASS — 80.39% branch-aware.
pyright: PASS — final plugin Pyright, 0 errors/0 warnings.
ruff: PASS — final check and format after reformatting two tests.
dependency/security audit: LOCAL DRY-RUN ONLY — `pip-audit` collected 122 installed packages. The full vulnerability lookup was prohibited by the platform's external-data-disclosure policy even after explicit user approval.
local smoke: NOT RUN — no external recording provided.
OpenAI smoke or authorization status: NOT AUTHORIZED — no upload attempted.
fresh-agent local forward test: RAN AS NEGATIVE EVIDENCE — without the intentionally excluded installation, a blind fresh context did not discover the source-tree skill and proposed a different stack.
fresh-agent cloud refusal: PASS — blind fresh context requested explicit OpenAI upload authorization and an API key before any upload.
make test: PASS — 2271 passed, 40 skipped, 5 deselected (7 pre-existing warnings).
repository pyright: BASELINE FAILURE — three pre-existing errors outside the plugin: `psy_bot/jobs/reflect_cancellation.py` and two in `tests/api/test_ams_redact_endpoint.py`.
final reviews: PASS — manual source review; no CRITICAL/HIGH finding.
```

The final full pytest/coverage rerun passed after the cachebuster and metadata-contract assertion were added: 125 passed with 80.39% branch-aware coverage. The final manifest validator, Pyright, Ruff, skill validator, and `git diff --check` also passed.

## Final Approval

- [ ] Every source-spec acceptance criterion has concrete evidence. Installation, fresh-agent, smoke, audit, and repository gates remain unproven as documented above.
- [x] No audio, secret, transcript, model cache or runtime state is staged.
- [ ] Commits are coherent, semantic and contain no AI attribution. No commit was created because the worktree already contains unrelated user changes.
- [x] The isolated plugin changes no `psy_bot` logic or project app configuration.
- [ ] Development plan and all five checklists are complete. Stage 5 remains incomplete only for the explicitly documented blocked/excluded checks.
