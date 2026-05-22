---
description: Synchronize .kb/ with changes in one or more corpus paths
argument-hint: one or more paths within the corpus (required)
---

Invoke the `kb-refresh` skill with the path(s) in `$ARGUMENTS`. Multiple paths may be passed in a single call (preferred over N sequential calls) — the skill batches the diff and advances state once.

If `$ARGUMENTS` is empty, ask the user which path(s) to refresh. Do not default to the whole corpus.
