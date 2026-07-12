# Transcribing Audio Plugin Migration Checklist

- [x] Target contains the complete source plugin and design specification without generated artifacts.
- [x] Target marketplace exposes both the existing umbrella and `transcribing-audio`.
- [x] Relocated manifest and embedded skill validate successfully.
- [x] Plugin tests, type checks, lint, formatting, and JSON checks pass from the target.
- [x] Source plugin, source marketplace entry, design specification, and historical plan directory are removed only after target verification.
- [x] Both repositories have focused semantic commits; the target commit is pushed to GitHub.
