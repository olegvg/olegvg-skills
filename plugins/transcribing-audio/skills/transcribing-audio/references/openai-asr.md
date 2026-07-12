# OpenAI ASR

## Supported request contract

This runtime selects `whisper-1` for OpenAI mode because its required canonical word timestamps use `response_format=verbose_json` and `timestamp_granularities=[word, segment]`. The current OpenAI documentation limits timestamp granularities to `whisper-1`; newer transcription models do not meet this plugin's mandatory word-timestamp contract.

The plugin sends only an ASR request. It never uses cloud diarization: speaker diarization remains local through pyannote in every mode. The per-chunk ceiling is `24000000` bytes, deliberately below OpenAI's documented 25 MB upload limit. Normalized chunks are FLAC; OpenAI documents FLAC, MP3, MP4, MPEG, MPGA, M4A, OGG, WAV, and WebM inputs.

## Consent, credentials, and failures

Before opening an audio file for upload, require a selected dotenv `OPENAI_API_KEY` and explicit upload consent. A TTY explanation must say that chunks are sent to OpenAI and accept only `y` or `yes`; non-TTY mode requires `--allow-cloud-upload`. Never put a key in a command, log, fingerprint, transcript, or error.

Provider authentication, permission, request-size, malformed-response, and rate/provider failures stop the run with a redacted error. There is no hidden provider retry. The pipeline's single quality recovery pass may reprocess only failed local intervals, then validates the complete result again.

## Opt-in network smoke

Only with the user's explicit approval and a short non-sensitive recording, use an interactive terminal and the resolved launcher with `--mode openai --allow-cloud-upload`. Confirm the final canonical JSON has word timestamps, the OpenAI ASR provenance, and local pyannote provenance. Do not run this smoke merely because a key might be present.

See OpenAI's [speech-to-text guide](https://developers.openai.com/api/docs/guides/speech-to-text) and [transcription API reference](https://developers.openai.com/api/reference/resources/audio/subresources/transcriptions/methods/create) for the current provider API.
