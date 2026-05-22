# <Topic>

One-paragraph orientation: what this file covers, why it exists, who cares.

## <Section 1>

Prose explaining the first concept. Concrete. Refer to source code by symbol name (`run_analysis`, `_safe_serp_search`, the `BillingService` class) so the prose survives renames and reorderings. Do not scatter `path/to/file.ext:123` line citations through the body — they go stale on every nontrivial edit and force full rewrites instead of targeted patches.

## <Section 2>

More prose. Keep to one topic per file. If you're tempted to add a section about an unrelated concern — that's a new leaf, not a new section here.

```mermaid
flowchart LR
    A[Source] --> B[Process]
    B --> C[Output]
```

## References

Collect precise locations here, grouped by symbol or section so a refresh can update line numbers without touching the body:

- Source: `path/to/real/file.ext` — `<symbol_a>` at L42, `<symbol_b>` at L101–L140.
- Tests: `path/to/test_file.ext`.
- Related: [<other-leaf>](../<other-area>/<other-leaf>.md)

<!--
No hard size limit. But if you're covering multiple independent topics, split.

Summary stability contract (see docs/concept.md):
- Reference code by symbol name in the body.
- Pin line numbers only in this `## References` block, grouped by symbol.
- This lets kb-refresh patch the References block without touching paragraphs.
-->
