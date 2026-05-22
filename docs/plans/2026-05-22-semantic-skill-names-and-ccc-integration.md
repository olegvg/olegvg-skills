# 2026-05-22 — Semantic Skill Names and ccc-Assisted KB Maintenance

## Goal

Make the runtime skill surface easier to understand and prepare the plugin for optional `ccc` semantic retrieval without introducing a separate `kbctl` tool.

This plan folds in four accepted maintenance-flow recommendations:

- `kb-refresh` should surface decision-record candidates but not record them.
- `kb-record-decision` should recommend follow-up refreshes but not advance state.
- Cross-skill recommendations should stay explicit and user-approved.
- A thin `kb-maintain` orchestrator should coordinate drift checks, refreshes, and decision recording without merging the atomic skills.

It also captures the `ccc` indexing constraint discovered during evaluation: a fresh `.cocoindex_code/settings.yml` excludes hidden directories via `**/.*`, which means `.kb/` is not indexed unless settings are repaired.

## Rename Map

Public skill and command names should describe the user-visible action:

| Old name | New name | Meaning |
|---|---|---|
| `kb-ingest` | `kb-build` | Build a fresh `.kb/` from a corpus |
| `kb-lint` | `kb-refresh` | Synchronize `.kb/` with source changes |
| `kb-distill` | `kb-record-decision` | Preserve shipped decisions from completed plans |

`kb-check-drift` remains read-only. `kb-query` remains the navigation skill. `kb-maintain` is added as a guided orchestrator.

The `.kb-state.json` fields remain `last_linted_sha` and `last_linted_at` for compatibility. Skills should describe them as the refresh watermark until a deliberate schema migration exists.

## Atomic Skill Contracts

### `kb-build`

Builds `.kb/` from scratch using the existing three-pass shape:

1. Main-agent survey and semantic grouping.
2. Per-domain subagent summary creation.
3. Main-agent index assembly and `.kb-state.json` initialization.

It must still exclude dated plans/specs from source summarization. Completed plans become durable knowledge only through `kb-record-decision`.

### `kb-refresh`

Reads the diff from `last_linted_sha` to `HEAD` for a scoped path, updates affected summaries/indexes, and advances `.kb-state.json`.

New behavior:

- During diff review, scan for completed plan candidates.
- If a completed plan lacks a matching `.kb/decisions/<YYYY-MM-slug>.md`, report `/kb-record-decision <plan-path>` as a follow-up.
- Never write decision records inside refresh.
- Never advance state until summaries/indexes are actually accurate.

### `kb-record-decision`

Reads a completed plan, writes one or more standalone decision records, and links them from affected summaries.

New behavior:

- Never advance `.kb-state.json`.
- After updating summaries, check whether affected source paths were refreshed.
- If not, recommend `/kb-refresh <affected-path>`.
- Do not run refresh automatically unless the user explicitly asked for the full maintenance flow.

### `kb-maintain`

Coordinates:

1. `kb-check-drift`
2. user-approved `kb-refresh <path>` commands
3. user-approved `kb-record-decision <plan-path>` commands

It does not implement the low-level logic itself. It keeps write boundaries visible so the user can review each mutation.

## ccc Integration Plan

`ccc` should be treated as an optional semantic scout for skills, not as a replacement for the three-layer navigation rules.

### When to use `ccc`

- Before a scoped refresh, to find likely affected summaries when path references are incomplete.
- During query fallback, after indexes-first navigation fails or the query is abstract.
- During maintenance, to find decision or summary candidates by meaning.

Recommended queries:

```bash
ccc search --path '.kb/indexes/**' --lang markdown '<query>' --limit 8
ccc search --path '.kb/summaries/**' --lang markdown '<query>' --limit 12
ccc search --path '.kb/decisions/**' --lang markdown '<query>' --limit 8
```

For code implementation lookup, pair KB search with a second pass over code:

```bash
ccc search '<domain query implementation>' --limit 12
```

Always verify `ccc` candidates by opening the returned files. `ccc` is recall, not truth.

### Required ccc preflight

Before any skill relies on `ccc`, check:

```bash
ccc doctor
ccc status
```

If `.kb/` files are absent from the index, inspect `.cocoindex_code/settings.yml`.

Fresh `ccc init` settings may include:

```yaml
exclude_patterns:
- '**/.*'
```

That pattern excludes `.kb/`. Replace it with explicit hidden service directories, while leaving `.kb/` indexable:

```yaml
exclude_patterns:
- '**/.agents'
- '**/.agents/**'
- '**/.claude'
- '**/.claude/**'
- '**/.codex'
- '**/.codex/**'
- '**/.git'
- '**/.git/**'
- '**/.github'
- '**/.github/**'
- '**/.cocoindex_code'
- '**/.cocoindex_code/**'
- '**/.playwright'
- '**/.playwright/**'
- '**/.playwright-cli'
- '**/.playwright-cli/**'
- '**/.playwright-mcp'
- '**/.playwright-mcp/**'
- '**/.venv'
- '**/.venv/**'
- '**/.mypy_cache'
- '**/.mypy_cache/**'
- '**/.pytest_cache'
- '**/.pytest_cache/**'
- '**/.ruff_cache'
- '**/.ruff_cache/**'
- '**/.tox'
- '**/.tox/**'
- '**/.vscode'
- '**/.vscode/**'
- '**/.worktrees'
- '**/.worktrees/**'
- '**/__pycache__'
- '**/node_modules'
- '**/target'
- '**/build/assets'
- '**/dist'
- '**/vendor/*.*/*'
- '**/vendor/*'
- '**/.kb/.kb-state.json'
- '**/.kb/**/.cache/**'
- '**/.kb/**/tmp/**'
- '**/.kb/**/raw/**'
- '**/.kb/**/archive/**'
```

Then run:

```bash
ccc index
ccc search --path '.kb/**' --lang markdown 'overview' --limit 3
```

The expected result is that `.kb/indexes`, `.kb/summaries`, and `.kb/decisions` are searchable, while state/cache/raw/archive material is not.

### ccc daemon behavior

Observed behavior on a large edge-case KB:

- Warm search is fast enough for skill use.
- Cold first search after daemon restart can take several seconds while the embedding model loads.
- Incremental `ccc index` is cheap when nothing changed.

Skill guidance:

- Prewarm when a maintenance flow starts: `ccc status` plus a tiny `.kb/indexes/**` search.
- Do not pass `--refresh` on every search. Run `ccc index` once at the start of a maintenance flow or after writes.
- If using `cocoindex_code.client.search(...)` directly, pass an absolute `project_root`; relative `.` can be interpreted as a second project and fail in daemon state.

## Abstract Query Handling

`ccc` can return confident but irrelevant chunks when the query is too abstract. Skills should use a relevance gate:

- Top results must contain domain terms from the query or clear synonyms.
- Results should converge on a small set of files or areas.
- Reference-only chunks should not be accepted as sufficient evidence.

If the gate fails, decompose the query into 2-4 probes:

```bash
ccc search --path '.kb/**' --lang markdown '<concept A synonyms>' --limit 10
ccc search --path '.kb/**' --lang markdown '<concept B concrete terms>' --limit 10
ccc search --path '.kb/**' --lang markdown '<workflow or implementation terms>' --limit 10
rg -n '<exact terms>|<aliases>' .kb docs src tests
```

If the probes still do not converge, say the KB lacks explicit coverage and answer only from opened sources or ask the user to narrow the question.

## Universal `.kb/` Structure

The target structure remains:

```text
.kb/
  indexes/
    _root.md
    <area>.md
  summaries/
    <area>/
      overview.md
      <topic>.md
  decisions/
    YYYY-MM-<slug>.md
  .kb-state.json
```

Optional future additions:

```text
.kb/glossary.md
.kb/aliases.md
```

These should be markdown so `ccc` can index them. Avoid JSON unless it is operational state.

## Edge-Case Lessons

The evaluated complex KB had:

- a route layer (`indexes/`)
- a large primary retrieval layer (`summaries/`)
- decision records linked from summaries
- many `References` sections

This catches most smaller corpora. The main retrieval issue was not size; it was noisy chunks from reference-heavy sections and abstract queries. Recommended mitigations:

- Search `indexes/` first for routing.
- Search `summaries/` for primary facts.
- Search `decisions/` for rationale.
- Treat `References` hits as pointers, not final answers.
- Consider a future section-aware markdown chunker only if noisy chunks repeatedly beat content chunks.

## Acceptance Criteria

- Public docs and commands use `kb-build`, `kb-refresh`, and `kb-record-decision`.
- `kb-maintain` exists as a thin orchestrator and does not hide writes.
- `kb-refresh` reports decision candidates without recording them.
- `kb-record-decision` reports refresh follow-ups without advancing state.
- The ccc plan explicitly accounts for default hidden-directory exclusion of `.kb/`.
- Skills preserve the core invariant: `.kb/` lives in the target corpus, not in this plugin.
