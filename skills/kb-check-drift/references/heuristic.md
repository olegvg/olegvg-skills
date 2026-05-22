# Drift Heuristic — Signals and Tuning

The heuristic is a **checklist** the agent applies after running `git log --stat <last_linted_sha>..HEAD`. It is policy, not code — users tune it by editing this file (or the main `SKILL.md`).

Default thresholds and the rationale for each signal are below. Skip a signal entirely if it never fires for the user's corpus; add one if the user's corpus has a structural signal not listed.

## Signals

### 1. New files above threshold

If a single directory or area saw **≥ 5 new files** since the last refresh, flag that area as a refresh candidate.

**Why.** Five files in one area usually means a new subdomain landed. Existing summaries probably do not cover it; the area index probably does not list it.

**Tuning.** Lower the threshold (e.g., 3) for small/early corpora; raise it (10) for active corpora where 5 new files is noise.

### 2. File renames or moves

Any rename or move under a directory referenced in `.kb/indexes/` is a flag.

**Why.** Index references mention paths; a rename turns those references into broken pointers. A refresh repoints them.

**Tuning.** None. This signal is deterministic — it fires only when a rename actually crosses an index-referenced path.

### 3. Changes to files referenced by existing indexes

Grep `.kb/indexes/` for paths in the changed-file list. Any hit is a flag.

**Why.** If the index points at a file and the file changed, the index entry's description may be wrong.

**Tuning.** None. Index entries are signposts; they rarely need updates from a content change, but worth surfacing.

### 4. Changes to files referenced by existing summaries

Grep `.kb/summaries/` for paths in the changed-file list. Any hit is a flag.

**Why.** Summaries cite specific files. A changed file may have altered the topic the summary covers.

**Tuning.** This signal fires often by design — every meaningful code change touches a summary. Do not weaken it; the refresh skill's job is to handle the volume.

### 5. New top-level directory

A new directory at the corpus root that did not exist at `last_linted_sha`.

**Why.** A new top-level directory may indicate a new area — the user may need a new index entry, not just a refreshed summary.

**Tuning.** None. Rare event; usually worth a flag.

### 6. Migration / schema files

Files matching `migrations/**`, `*.sql`, `schema.*`, or similar data-shape markers. Any change is a flag for any area that touches data.

**Why.** Data-shape shifts have semantic consequences across the codebase that a file-only grep misses.

**Tuning.** Add or remove glob patterns to match the user's corpus (e.g., `*.proto`, `*.graphql`, `models/**`).

### 7. Deleted files referenced in `.kb/`

A file that existed at `last_linted_sha` but is gone at HEAD, and `.kb/` still mentions it. **Hard flag.**

**Why.** A summary or index points at a file that does not exist. The KB is wrong, not stale — fix it before relying on the KB.

**Tuning.** None. This signal is binary and always meaningful.

### 8. Completed plan with no decision record

A plan file under `docs/plans/` (or similar) whose sibling `checklist-*.md` has all items ticked, and no matching file exists in `.kb/decisions/` (match by slug). **Soft flag.**

**Why.** Not every plan yields a durable decision, but a complete plan worth recording should produce a record. Soft flag — the user decides.

**Tuning.** Adjust the path pattern (`docs/plans/**`, `journal/plans/**`, etc.) to match the corpus convention. Detect "complete" by absence of `^- \[ \]` lines in the sibling checklist.

## What "policy, not code" means

The signals above describe what to *look for*. The agent applies them by running `git log --stat`, `grep`, and `ls` — there is no parser, no schema, no config file. To change behavior, edit the SKILL.md or this references file. That is the intended extension point.

Resist adding a YAML config (`.kb-drift-config.yaml`) or environment variables. The signals are short prose that the agent reads each invocation; adding config moves them out of LLM-reachable instructions and into machine-only state, which the agent then cannot reason about.
