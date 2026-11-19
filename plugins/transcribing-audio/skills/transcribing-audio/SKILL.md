---
name: transcribing-audio
description: Transcribe audio recordings into word-timestamped, speaker-labelled JSON and readable text with local or OpenAI ASR plus local diarization. Use for voice memos, meetings, interviews, calls, multi-speaker recordings, transcription requests, diarization requests, speaker labels, subtitles, resumable audio processing, or suspected ASR repetition and hallucination loops.
metadata:
  internal: true
---

# Transcribing Audio

## Safety and privacy

- Resolve the input and output paths without copying audio into the repository.
- Keep audio local by default. Never infer permission to upload it: before OpenAI mode, explain that audio chunks leave the machine and obtain explicit consent.
- Never print dotenv values or commit audio, transcripts, runtime state, or model caches.
- Treat raw diarization labels as labels, not identities. Apply `--speaker-names` only after diarization returns those raw labels.

## Choose the mode

- Select local ASR when the user requires local processing or has not explicitly approved an upload. Pass `--mode local` when stdin is not a TTY.
- Use OpenAI ASR only after explicit consent. A TTY run prompts for the ASR mode and accepts `--mode` as a default. A non-TTY run requires an explicit mode and needs `--allow-cloud-upload` for OpenAI.
- Use `--speakers N` for an exact count or omit the speaker flags for automatic diarization. TTY runs accept `auto`, `N` or `MIN-MAX`. Non-TTY runs accept either or both of `--min-speakers` and `--max-speakers`.

## Run the pipeline

Set `SKILL_DIR` from the absolute directory containing this loaded `SKILL.md`; do not derive it from the shell working directory or `$0`.

```sh
SKILL_DIR="<absolute path to this skill directory>"
"$SKILL_DIR/../../scripts/transcribe_audio.py" --help
```

The first launch can prepare the runtime even for `--help`. Resume is enabled
by default and can be requested explicitly with `--resume`. It validates prior
committed stages before reuse. TXT, SRT, and VTT are derived from validated
canonical JSON.

## Stop conditions

- Stop before any upload if consent is absent, declined, or ambiguous.
- Stop and report the recorded intervals if the one allowed quality retry fails. Do not present derived output as successful.
- Stop on unsafe paths, missing prerequisites, failed local model access, or a provider failure; report the redacted error and the safe recovery option.

## Common commands

Replace the placeholders with real paths. The first command is interactive; every TTY run still asks for input, mode, and speaker policy.

```sh
# Interactive run with local selected as the default
"$SKILL_DIR/../../scripts/transcribe_audio.py" /absolute/path/recording.wav --mode local

# Explicit non-interactive local run
"$SKILL_DIR/../../scripts/transcribe_audio.py" /absolute/path/recording.wav \
  --mode local --output-dir /absolute/path/output --language ru \
  --local-model large-v3-turbo --speakers 2 --speaker-names "SPEAKER_00=Alex,SPEAKER_01=Sam" \
  --resume --srt --vtt

# Ranged or automatic speaker counts
"$SKILL_DIR/../../scripts/transcribe_audio.py" /absolute/path/meeting.wav \
  --mode local --min-speakers 2 --max-speakers 4 --overwrite
"$SKILL_DIR/../../scripts/transcribe_audio.py" /absolute/path/memo.wav --mode local

# Explicit non-interactive OpenAI run, only after upload consent
"$SKILL_DIR/../../scripts/transcribe_audio.py" /absolute/path/non-sensitive.wav \
  --mode openai --openai-model whisper-1 --env-file /absolute/path/credentials.env \
  --allow-cloud-upload

# Reprobe an unhealthy local runtime component
"$SKILL_DIR/../../scripts/transcribe_audio.py" /absolute/path/recording.wav \
  --mode local --reprobe
```

Use `--help` for the complete flag contract. The current launcher accepts
`--debug` as a reserved flag.

## Read references only when needed

Read only the rows needed for the current request.

| Need | Read |
| --- | --- |
| Runtime fingerprint, probe, cached venv, backend fallback, reprobe | [runtime and backends](references/runtime-and-backends.md) |
| MLX/faster-whisper models, language and independent windows | [local ASR](references/local-asr.md) |
| OpenAI model capability, upload consent, chunks and API errors | [OpenAI ASR](references/openai-asr.md) |
| pyannote speaker counts, raw labels, alignment and names | [diarization and alignment](references/diarization-and-alignment.md) |
| Gate definitions, thresholds, retries and unresolved failures | [quality and recovery](references/quality-and-recovery.md) |
| Canonical JSON, TXT/SRT/VTT fields and validation | [output schema](references/output-schema.md) |
