---
name: transcribing-audio
description: Transcribe audio recordings into word-timestamped, speaker-labelled JSON and readable text with local or OpenAI ASR plus local diarization. Use for voice memos, meetings, interviews, calls, multi-speaker recordings, transcription requests, diarization requests, speaker labels, subtitles, resumable audio processing, or suspected ASR repetition and hallucination loops.
---

# Transcribing Audio

## Safety and privacy

- Resolve the input and output paths without copying audio into the repository.
- Keep audio local by default. Never infer permission to upload it: before OpenAI mode, explain that audio chunks leave the machine and obtain explicit consent.
- Never print dotenv values or commit audio, transcripts, runtime state, or model caches.
- Treat raw diarization labels as labels, not identities. Apply `--speaker-names` only after diarization returns those raw labels.

## Choose the mode

- Use local ASR when the user requires local processing or has not explicitly approved an upload.
- Use OpenAI ASR only after explicit consent. Every TTY run asks for local/OpenAI even when `--mode` supplies a default; a non-TTY OpenAI run requires `--allow-cloud-upload`.
- Select `--speakers N` for an exact count, `--min-speakers` with optional `--max-speakers` for a range, or omit speaker flags for automatic diarization.

## Run the pipeline

Set `SKILL_DIR` from the absolute directory containing this loaded `SKILL.md`; do not derive it from the shell working directory or `$0`.

```sh
SKILL_DIR="<absolute path to this skill directory>"
"$SKILL_DIR/../../scripts/transcribe_audio.py" --help
```

Run the launcher from that resolved path. Use `--resume` after an interruption; it validates and reuses prior committed stages. Canonical JSON is authoritative; TXT, SRT, and VTT are derived only after the JSON validates.

## Stop conditions

- Stop before any upload if consent is absent, declined, or ambiguous.
- Stop and report the exact failed intervals if the one allowed quality retry remains unresolved. Do not present derived output as successful.
- Stop on unsafe paths, missing prerequisites, failed local model access, or a provider failure; report the redacted error and the safe recovery option.

## Common commands

Replace the placeholders with real paths. The first command is interactive; every TTY run still asks for input, mode, and speaker policy.

```sh
# Interactive local run
"$SKILL_DIR/../../scripts/transcribe_audio.py" /absolute/path/recording.wav

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
  --allow-cloud-upload --debug

# Reprobe an unhealthy local runtime component
"$SKILL_DIR/../../scripts/transcribe_audio.py" /absolute/path/recording.wav \
  --mode local --reprobe
```

Use `--max-speakers` without `--min-speakers` for an upper bound. Use `--help` for the complete flag contract.

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
