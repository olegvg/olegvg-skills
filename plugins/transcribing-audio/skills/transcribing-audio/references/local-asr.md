# Local ASR

## Backends and models

The default local model is `large-v3-turbo`. The runtime uses MLX Whisper `>=0.4.3,<0.5` for MLX or faster-whisper `>=1.2.1,<2` for CUDA/CPU. Use the model identifier accepted by the selected backend through `--local-model`; keep model downloads in the normal persistent user cache.

Both adapters require word timestamps and pass `condition_on_previous_text=false`. This makes independently retried windows safe to merge and prevents prior chunk text from causing a continuation loop. The default maximum window is `600.0` seconds with `2.0` seconds overlap. Language is auto-detected when `--language` is absent; pass an ISO language code to pin it.

CUDA uses `float16`; CPU uses `int8`. MLX is selected only on a healthy supported Apple-Silicon host. The backend choice does not control the separate pyannote device.

With the locked MLX Whisper 0.4.3, decoding rejects the beam size this runtime
passes, even when the hardware probe succeeds and a valid MLX model is selected.

## Optional model smoke

Use an external, non-sensitive recording and an already-authorized model on a
host that selects CPU or CUDA. Run the resolved launcher in a terminal with
`--mode local` and an exact `--speakers` count. Check the ASR backend, model,
detected language, and separate diarization device in the canonical JSON.

Read the primary backend documentation when changing a model or its capabilities: [MLX Whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper) and [faster-whisper](https://github.com/SYSTRAN/faster-whisper).
