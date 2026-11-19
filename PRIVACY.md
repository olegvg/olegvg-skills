# Privacy

OlegVG Skills provides agent instructions, references, templates and an independent audio-transcription runtime. The instruction package operates no backend or telemetry endpoint and requires no package API key. The release tooling runs locally with Python's standard library and Git.

Your chosen agent host processes prompts, corpus excerpts and tool results under its own account, retention and privacy settings. A local skill installation does not make that host processing local. Enabled file, network, model and upload tools retain their own behavior and permissions.

KB files belong in `.kb/` inside your selected corpus, never in an installed plugin or cache. Summaries and decision records can expose private source information: consider workspace sharing, backups and version control before saving or publishing them. Do not put private inputs, recordings, transcripts, credentials or generated KBs in public issues, examples or release assets.

The `mobile-test-environments` discovery helper reads local tool paths, virtual-device names/identifiers and device states. It queries ADB on IPv4 loopback, using `ANDROID_ADB_SERVER_PORT` when set. It skips discovery for a custom `ADB_SERVER_SOCKET`. Inspect other endpoint configuration explicitly. Mobile screenshots and logs can contain personal data. Use synthetic fixtures, keep evidence in the task workspace, and redact it before sharing. Keep device evidence and tool/runtime downloads out of release assets.

Choose local ASR to transcribe on the machine. OpenAI ASR requires explicit
consent before sending chunks, including chunks retried after quality checks.
The runtime can download dependencies and models. Both modes need Hugging Face
model access for local diarization. With its default telemetry setting,
pyannote can send usage metadata such as the pipeline identifier, recording
duration, and requested speaker counts. See the [pyannote telemetry documentation](https://github.com/pyannote/pyannote-audio#telemetry).

The runtime creates a plugin-local `.venv` and can retain normalized audio,
chunks, transcripts, and run state in its private temporary directory for
resume. Choose an output directory outside the plugin and manage the retained
files under your own retention policy. Keep dotenv values private. Local
diarization labels do not establish a speaker's identity.

Removing a skill or plugin does not delete your corpus, generated KBs, recordings, transcripts, host conversations or provider records. Manage those files, backups and retention through their respective controls. The maintainer has no access to them through this repository.

Report package issues using redacted or synthetic examples through the [repository](https://github.com/olegvg/olegvg-skills/issues).
