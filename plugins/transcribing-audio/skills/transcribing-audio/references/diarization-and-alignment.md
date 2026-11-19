# Diarization and alignment

## Local pyannote contract

The local diarizer uses `pyannote/speaker-diarization-community-1` at revision `3533c8cf8e369892e6b79ff1bf80f7b0286a54ee`. It requires gated-model access through `HF_TOKEN`. It runs on the runtime's independently selected MPS, CUDA, or CPU device and never receives an OpenAI credential.

`--speakers N` sends matching `min_speakers=N` and `max_speakers=N`. A non-TTY run
can pass either or both bounds. A TTY run takes both bounds as `MIN-MAX`.
An automatic request leaves both unset. The runtime validates the raw label
count against an exact count or any supplied bounds.

Raw labels such as `SPEAKER_00` are opaque output labels. `--speaker-names`
accepts labels assigned to at least one transcript word and maps each to a
unique display name. Do not create biometric speaker profiles or infer
real-world identities.

## Word alignment

Each word is assigned to the overlapping diarization turn with the largest overlap. Ties resolve by earlier turn start then raw label. A word with no overlap uses the nearest turn, again resolving ties by start then raw label. Adjacent words become one transcript turn only when raw and display speaker labels agree and their gap is at most `1.5` seconds.

The canonical output retains both `raw_speaker` and `speaker`; renaming changes only the latter. This preserves reproducible alignment while presenting user-supplied display names in TXT, SRT, and VTT.
