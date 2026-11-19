# Quality and recovery

`QualityPolicy(version="1")` is implemented in `audio_transcriber.quality`; the values below document the checked runtime contract.

| Setting | Value | Purpose |
| --- | ---: | --- |
| `version` | `1` | Record the policy used for a report. |
| `timestamp_epsilon_s` | `0.05` | Tolerate small timestamp boundary error. |
| `silence_mean_volume_dbfs` | `-50.0` | Require measured silence for an empty result unless backend no-speech evidence is present. |
| `max_segment_duration_s` | `60.0` | Reject oversized ASR segments. |
| `max_words_per_second` | `8.0` | Detect implausibly fast output. |
| `ngram_sizes` | `(3, 4, 5, 6)` | Check repeated consecutive token n-grams. |
| `max_consecutive_ngram_repeats` | `3` | Bound allowed consecutive n-gram repeats. |
| `min_unique_token_ratio` | `0.2` | Minimum token diversity for sufficiently long output. |
| `unique_ratio_min_tokens` | `20` | Minimum tokens before diversity applies. |
| `max_compression_ratio` | `2.4` | Detect highly repetitive text. |
| `low_confidence_probability` | `0.15` | Mark a timestamped word as low confidence below this value. |
| `max_low_confidence_fraction` | `0.5` | Bound low-confidence word share. |
| `min_confidence_word_count` | `10` | Minimum words before confidence applies. |
| `min_confidence_coverage_fraction` | `0.8` | Minimum non-null confidence coverage before confidence applies. |
| `retry_window_s` | `15.0` | Use smaller independent recovery windows. |
| `retry_overlap_s` | `0.5` | Preserve bounded overlap between recovery windows. |

Every planned chunk must produce exactly one matching ASR result. Empty output passes only with measured low volume or backend no-speech probability of at least `0.80`. The report runs these issue codes: `coverage`, `timestamps`, `silence`, `segment_duration`, `words_per_second`, `repetition`, `unique_token_ratio`, `compression_ratio`, and `confidence`. Issues carry intervals and chunk identifiers. Transcript-wide repetition, diversity, compression, and confidence checks associate their findings with the first chunk for recovery.

On a failure, the pipeline retries the affected chunks once with the selected
ASR mode, 15-second windows, 0.5-second overlap, and temperature zero. The
runtime passes a beam size of five to local adapters. It runs every gate again
on the full result and records unresolved intervals before stopping.

The deterministic Russian repetition fixture exercises the loop detectors without embedding user audio. It protects against repeated ASR phrases while keeping the acceptance test offline and reproducible.
