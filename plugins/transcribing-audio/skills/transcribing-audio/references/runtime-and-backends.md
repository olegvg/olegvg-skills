# Runtime and backends

## Supported host and prerequisites

Version 1 supports macOS and Linux, not Windows. On macOS Apple Silicon with macOS 14 or newer, it prefers MLX ASR. On Linux with a healthy `nvidia-smi` probe, it chooses CUDA ASR. Otherwise it uses CPU ASR. pyannote uses a separately selected compute device: MPS/CUDA when healthy, otherwise CPU.

Require Python 3.13, `uv`, `ffmpeg`, and `ffprobe`. Local diarization additionally needs approved Hugging Face access through `HF_TOKEN`; OpenAI mode also needs the local diarizer. Validate these requirements before normalization, ASR, or any upload.

## Reusable runtime and recovery

The launcher owns one plugin-local `.venv`. Its base fingerprint hashes runtime version `1`, the lockfile, operating-system version, architecture, and Python version. The runtime fingerprint adds the chosen ASR backend and pyannote device. A verified cached fingerprint skips a full probe and sync; `--reprobe` refreshes the hardware decision without creating a second virtual environment.

Mutable coordination state is private to `/tmp/transcribing-audio-<uid>/`: the root, runtime children, locks, and run state are user-owned and mode `0700`. State schema version `1` and the runtime index identify the reusable cached runtime. Do not edit these files, follow symlinks, or move audio into this directory.

If a local ASR backend or pyannote device fails before audio work, it is recorded as unhealthy, excluded on the next probe, and the launcher re-executes once. A second recovery failure stops. Use `--reprobe` only after fixing the underlying host/model issue; it clears the recorded exclusions before re-probing.

## Caches and safe recovery

Keep downloaded models in their providers' persistent user caches, never in `/tmp` or the repository. A safe first recovery is to check `uv`, `ffmpeg`, `ffprobe`, model access, and the source file, then run the resolved launcher with `--reprobe`. Do not delete the shared runtime directory or the plugin `.venv` while a run is active.

The runtime has an ordinary cheap index, a base fingerprint, and a backend/device runtime fingerprint. This preserves a stable cache while correctly rebuilding after a lockfile, host, Python, or capability change.
