# Transcribing Audio Plugin Stage 1 Verification Checklist

> Evidence was reset and re-executed on 2026-07-11. Checked items below have direct command or test evidence; the external fresh-context baseline remains pending explicit consent because it could export private audio to a model service.

## Deliverable Summary

Stage 1 establishes the repository-local plugin, immutable contracts, safe dotenv configuration, deterministic MLX/CUDA/CPU probing, and one reusable Git-ignored virtual environment at `plugins/transcribing-audio/.venv/`. Runtime state remains private under `/tmp/psy-audio-transcriber-<uid>/` and never creates backend-specific environments.

## Dependency and Baseline Evidence

- [x] Supported Python/OS/architecture matrix is recorded from current primary docs.
- [x] One plugin `uv.lock` resolves base, MLX and faster-whisper environments.
- [x] OpenAI word-timestamp model/format and current chunk limit policy are recorded.
- [ ] Fresh-context baseline prompt and date are recorded without audio, transcript, or secrets.
- [x] Stage 5 forward test input is `docs/transcripts/Sherif Khimshiashvili Street.m4a` with exactly 3 speakers.
- [x] The uneven speaker distribution is recorded as an acceptance caveat.
- [ ] Baseline omissions are marked from a real fresh-context result.

```text
Compatibility decision, rechecked 2026-07-11:
- Python: >=3.13,<3.14. Current package metadata and a universal resolution support it.
- Direct ranges: openai >=2.45.0,<3; pyannote.audio >=4.0.7,<5;
  python-dotenv >=1.2.2,<2; torch >=2.8,<3; faster-whisper >=1.2.1,<2
  on macOS/Linux; mlx-whisper >=0.4.3,<0.5 on macOS arm64.
- `uv lock --project plugins/transcribing-audio --python 3.13` resolved 145 packages.
  The committed lock selected openai 2.45.0, pyannote-audio 4.0.7,
  python-dotenv 1.2.2, torch 2.13.0, faster-whisper 1.2.1 and mlx-whisper 0.4.3.
- Local MLX support requires native Apple Silicon, macOS >=14 and verified Metal; CUDA requires
  a healthy Linux NVIDIA probe. CPU remains the safe fallback. `ffmpeg` and `ffprobe` are required.
- Diarization uses `pyannote/speaker-diarization-community-1` at revision
  `3533c8cf8e369892e6b79ff1bf80f7b0286a54ee`; gated access needs HF_TOKEN.
- OpenAI word timestamps use whisper-1 with verbose_json and timestamp_granularities=[word].
  OpenAI publishes a 25 MB upload limit; the runtime policy keeps 24,000,000 bytes per chunk.

Forward-test selection supplied by the user:
- input: docs/transcripts/Sherif Khimshiashvili Street.m4a
- exact speakers: 3
- caveat: two speakers appear rarely and one speaks for almost all of the recording.
- safe inspection: AAC M4A, 9,296,050 bytes, 555.413333 seconds, stereo at 48 kHz.

Baseline attempt: an isolated `codex exec --ephemeral --ignore-user-config --sandbox read-only`
was first blocked by filesystem sandboxing. Escalation was rejected because that agent could read
the private audio and export it or a derived transcript to an external model service. No transcript,
output artifact, credential, or audio copy was created. Do not run this check without explicit user consent.
```

## Plugin, Marketplace, Scripts, and Isolation Checks

- [x] `.codex-plugin/plugin.json` exists and passes the canonical plugin validator.
- [x] Plugin folder, manifest, embedded skill and marketplace entry all use `transcribing-audio`.
- [x] Manifest points to `./skills/` and declares no absent apps, MCP servers, hooks or assets.
- [x] Marketplace preserves its metadata/order and contains local source `./plugins/transcribing-audio`, `AVAILABLE`, `ON_INSTALL` and a category.
- [x] Embedded `skills/transcribing-audio/` contains concise `SKILL.md` and generated `agents/openai.yaml`; detailed references are deliberately deferred to Stage 5.
- [x] Executable implementation lives in plugin-root `scripts/`; no duplicate runtime exists under the embedded skill.
- [x] Plugin contains no README, changelog, installation guide, app manifest, MCP manifest, hooks or placeholder assets.
- [x] `pyproject.toml` is independent and `uv.lock` is versioned in the Stage 1 commit.
- [x] No module imports `psy_bot` or reads `app_config_*.yaml`.
- [x] Exactly one plugin-local `.venv` exists and `plugins/transcribing-audio/.gitignore` ignores it.
- [x] Launcher and pre-runtime bootstrap are stdlib-only.
- [x] Launcher has an env-python shebang and executable permission.
- [x] Plugin root is derived from the launcher path, not repository cwd, and install paths are excluded from fingerprints.

## Contract and Configuration Checks

- [x] Persisted models are frozen, slotted and explicitly validated with exact schema keys.
- [x] ASR backend and diarization compute device are separate values.
- [x] Exact and range speaker counts are mutually exclusive and positive.
- [x] Dotenv discovery selects `.env` before fallback `.env.prod`.
- [x] Explicit `--env-file` bypasses discovery and missing files fail safely.
- [x] Ambient process secrets do not override the selected dotenv source.
- [x] Only `OPENAI_API_KEY` and `HF_TOKEN` are loaded from dotenv files.
- [x] Credentials are absent from repr, serialized configuration, recovery metadata and subprocess environments.

## Runtime Bootstrap Checks

- [x] MLX requires macOS >=14, arm64 and verified Metal.
- [x] CUDA requires a healthy bounded Linux NVIDIA probe.
- [x] CPU fallback records a safe reason.
- [x] Missing uv/ffmpeg/ffprobe, unsafe input, unsafe venv, or unsafe private root fails before provisioning.
- [x] Fingerprints cover runtime version, lock, OS version, architecture, backend, device and Python.
- [x] Valid runtime index plus the verified plugin-local executable skips the full probe and `uv sync`.
- [x] `--reprobe` triggers a targeted reprobe without creating a second environment.
- [x] Failed ASR backend or diarization device is durably excluded; one recovery re-exec is permitted and a second failure stops safely.
- [x] User `--reprobe` clears transient exclusions; recovery honors them; a base-fingerprint change ignores stale exclusions.
- [x] The private runtime root, nested runtime directories, state files and provision lock reject symlinks, require current-user ownership and use `0700` directories.
- [x] Provisioning always sets the absolute plugin-local `UV_PROJECT_ENVIRONMENT` and installs all extras into that one environment.
- [x] Bootstrap leaves persistent model-cache variables unchanged and never creates model-cache paths in runtime state or the virtual environment.

## Verification Evidence

- [x] Plugin-focused pytest: 42 passed; branch-aware coverage 83.70% (required >=80%).
- [x] Plugin pyright strict: 0 errors, 0 warnings.
- [x] Plugin Ruff check and format check pass.
- [x] Plugin manifest validator and embedded skill validator pass.
- [x] Launcher smoke: provision/re-exec used the one plugin `.venv` and rendered `--help`.
- [x] `git diff --check` passes.
- [x] An independent review found symlink, secret-environment, unsafe-input and recovery issues; regression tests now cover the fixes.

```text
Repository-wide make test: 2,271 passed, 40 skipped, 5 deselected.
Repository-wide uv run pyright: 3 pre-existing errors outside this plugin:
- psy_bot/jobs/reflect_cancellation.py: incompatible AsyncCallbackHandler override.
- tests/api/test_ams_redact_endpoint.py: two API-route typing errors.
The isolated plugin pyright gate is clean.
```

## Stage Approval

- [ ] The external fresh-context baseline and its omissions are still unverified without explicit consent to run it.
- [x] No unresolved CRITICAL/HIGH implementation finding remains after review and regression tests.
- [ ] Stage 2 may begin only after the baseline decision is recorded.
