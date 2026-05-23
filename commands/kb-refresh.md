---
description: Synchronize .kb/ with changes in one or more corpus paths
argument-hint: one or more paths within the corpus (recommended)
---

Invoke the `kb-refresh` skill with the path(s) in `$ARGUMENTS`. Multiple paths may be passed in a single call (preferred over N sequential calls) — the skill batches the diff and advances state once.

If `$ARGUMENTS` is empty:

1. Do **not** infer scope from `git status`, the working tree, or "everything since the watermark".
2. Do **not** default to the whole corpus, even in auto / non-interactive modes — that path leads straight to the scope-budget failure documented in the skill.
3. Invoke `kb-check-drift` first (the skill's step 0 does this) so the user can pick refresh candidates from a real report instead of letting the agent guess.

When the user supplies the path(s), the skill enforces a scope budget after the diff — if the change is too large for one refresh pass, it will stop and ask the user to narrow scope or split the work across multiple invocations / areas.
