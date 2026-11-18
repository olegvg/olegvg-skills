# Privacy

OlegVG Skills provides agent instructions, references, templates and an independent audio-transcription runtime. The instruction package operates no backend or telemetry endpoint and requires no package API key. The release tooling runs locally with Python's standard library and Git.

Your chosen agent host processes prompts, corpus excerpts and tool results under its own account, retention and privacy settings. A local skill installation does not make that host processing local. Enabled file, network, model and upload tools retain their own behavior and permissions.

KB files belong in `.kb/` inside your selected corpus, never in an installed plugin or cache. Summaries and decision records can expose private source information: consider workspace sharing, backups and version control before saving or publishing them. Do not put private inputs, recordings, transcripts, credentials or generated KBs in public issues, examples or release assets.

The `mobile-test-environments` discovery helper reads local tool paths, virtual-device names/identifiers and device states. It queries only the standard local ADB endpoint; custom endpoints require explicit inspection. Mobile screenshots and device logs can contain personal data: use synthetic fixtures, keep evidence in the task workspace, and redact it before sharing. No device evidence or tool/runtime downloads belong in release assets.

The independent `transcribing-audio` plugin uses local ASR by default. OpenAI ASR requires explicit consent before audio chunks leave the machine. Local backends can download models and dependencies from their providers; Hugging Face access and OpenAI ASR may require credentials. The runtime creates a plugin-local `.venv` cache; audio, output and resumable state belong outside the installed plugin. Do not print dotenv values. Local diarization labels do not establish a speaker's identity.

Removing a skill or plugin does not delete your corpus, generated KBs, recordings, transcripts, host conversations or provider records. Manage those files, backups and retention through their respective controls. The maintainer has no access to them through this repository.

Report package issues using redacted or synthetic examples through the [repository](https://github.com/olegvg/olegvg-skills/issues).
