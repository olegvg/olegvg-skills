# Runtime and backends

## Supported host and prerequisites

The launcher supports macOS and Linux. On Apple Silicon with macOS 14 or newer,
it probes MLX first. On Linux it chooses CUDA with a healthy `nvidia-smi` probe.
Other supported hosts use CPU ASR. pyannote selects its compute device
separately and uses MPS or CUDA when healthy, otherwise CPU.

Require Python 3.13, `uv`, `ffmpeg`, and `ffprobe`. Both modes need `HF_TOKEN`
with access to the gated Hugging Face diarization model. OpenAI mode also needs
`OPENAI_API_KEY`. The runtime loads credentials from one dotenv file selected
by `--env-file`, then falls back to `.env` or `.env.prod` in the installed plugin
root. Values in the process environment are not a credentials source.

## Reusable runtime and recovery

The launcher uses one locked, plugin-local `.venv` to isolate dependencies from
the surrounding project while using native GPU backends. Its base fingerprint
includes runtime version `1`, the lockfile, the host and Python version. The
runtime fingerprint adds the chosen ASR backend and pyannote device. A verified
cached fingerprint skips a full probe and sync. `--reprobe` refreshes the
hardware decision using the same environment.

Private state lives under `/tmp/transcribing-audio-<uid>/`. State directories
use mode `0700` and lock and state files use `0600`. State schema version `1` and
the runtime index identify reusable state. Runs can retain normalized audio,
FLAC chunks, and transcripts under `runs/<fingerprint>/`. The run fingerprint
uses input identity, the processing configuration, and the runtime fingerprint.
Leave these files under runtime control to preserve resume validation.

If a local ASR backend or pyannote device fails before audio work, it is recorded as unhealthy, excluded on the next probe, and the launcher re-executes once. A second recovery failure stops. Use `--reprobe` only after fixing the underlying host/model issue; it clears the recorded exclusions before re-probing.

## Caches and safe recovery

Keep downloaded models in their providers' persistent user caches, never in `/tmp` or the repository. A safe first recovery is to check `uv`, `ffmpeg`, `ffprobe`, model access, and the source file, then run the resolved launcher with `--reprobe`. Do not delete the shared runtime directory or the plugin `.venv` while a run is active.

The runtime has an ordinary cheap index, a base fingerprint, and a backend/device runtime fingerprint. This preserves a stable cache while correctly rebuilding after a lockfile, host, Python, or capability change.
