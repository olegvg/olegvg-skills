# OpenAI ASR

## Supported request contract

The OpenAI adapter accepts only `whisper-1`. It requests word and segment
timestamps with `response_format=verbose_json` and
`timestamp_granularities=[word, segment]`. OpenAI has scheduled `whisper-1` for
shutdown on February 26, 2027. See the [OpenAI deprecation schedule](https://developers.openai.com/api/docs/deprecations).

OpenAI receives ASR requests. Speaker diarization runs locally through pyannote
in both modes. The pipeline uploads normalized FLAC chunks below `24000000` bytes,
under the provider's documented 25 MB upload limit.

## Consent, credentials, and failures

Before opening an audio file for upload, require a selected dotenv `OPENAI_API_KEY` and explicit upload consent. A TTY explanation must say that chunks are sent to OpenAI and accept only `y` or `yes`; non-TTY mode requires `--allow-cloud-upload`. Never put a key in a command, log, fingerprint, transcript, or error.

The OpenAI SDK retries transient request errors by default. A final provider
error or malformed response stops the run with a redacted error. The pipeline
can also retry failed quality intervals with the original ASR mode. In OpenAI
mode, this uploads the affected subchunks under the same consent.

## Opt-in network smoke

Only with the user's explicit approval and a short non-sensitive recording, use an interactive terminal and the resolved launcher with `--mode openai --allow-cloud-upload`. Confirm the final canonical JSON has word timestamps, the OpenAI ASR provenance, and local pyannote provenance. Do not run this smoke merely because a key might be present.

See OpenAI's [speech-to-text guide](https://developers.openai.com/api/docs/guides/speech-to-text) and [transcription API reference](https://developers.openai.com/api/reference/resources/audio/subresources/transcriptions/methods/create) for the current provider API.
