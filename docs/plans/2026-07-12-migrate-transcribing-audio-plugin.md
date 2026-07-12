# Migrate the Transcribing Audio Plugin

## Context

Move the completed self-contained `transcribing-audio` Codex plugin out of
`psy_bot` into this repository so it can be installed from GitHub without
coupling its runtime, tests, or progressive-disclosure skill to a therapy-bot
checkout.

## Plan

1. Copy the plugin source, tests, lockfile, design specification, and historical
   implementation plan to `plugins/transcribing-audio/`, excluding virtual
   environments, caches, bytecode, recordings, runtime state, and generated
   transcript output.
2. Register `transcribing-audio` as a second local source in
   `.agents/plugins/marketplace.json`; preserve the existing umbrella entry and
   its order.
3. Update the standalone manifest owner and repository metadata for
   `olegvg/olegvg-skills`; preserve the public plugin and skill names while
   replacing internal `psy_bot` runtime names with neutral plugin names.
4. Validate the relocated plugin, embedded skill, targeted test suite, JSON
   manifests, and local marketplace discovery.
5. Remove the migrated plugin, marketplace entry, design specification, and
   historical plan directory from `psy_bot` only after target verification.
   Commit the target addition and source removal separately, then push the
   target repository for GitHub-based installation.

## Constraints

- Do not copy `.venv`, `.pytest_cache`, `.ruff_cache`, `__pycache__`, audio,
  dotenv files, runtime state, or transcript output.
- Do not alter unrelated `psy_bot` changes.
- Preserve `transcribing-audio` as a standalone plugin root so its bundled
  skill can resolve `../../scripts/transcribe_audio.py` after installation.
