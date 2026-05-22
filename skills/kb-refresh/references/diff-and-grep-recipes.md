# Diff and Grep Recipes

Exact shell commands the refresh workflow uses. Lifted out of `SKILL.md` so the main file describes the workflow and this file holds the mechanical details.

## Single-path diff (one scope)

```bash
git -C <corpus-root> diff <base_sha>..HEAD -- <path>
```

For human inspection of what changed:

```bash
git -C <corpus-root> diff --stat <base_sha>..HEAD -- <path>
```

## Multi-path batched diff (preferred)

When multiple paths are scoped to the same refresh, run **one** diff with all paths after `--`:

```bash
git -C <corpus-root> diff <base_sha>..HEAD -- <path1> <path2> <path3>
```

This is materially faster than N separate diffs and produces a single unified output the workflow processes once.

## File-status only (changed / renamed / deleted)

When you need just the file list, not the content:

```bash
git -C <corpus-root> diff --name-status <base_sha>..HEAD -- <paths...>
```

Output:

- `M <path>` — modified
- `A <path>` — added
- `D <path>` — deleted
- `R<NN> <old> <new>` — renamed (NN is similarity percentage)
- `C<NN> <orig> <copy>` — copied

The `R` and `D` lines are the inputs to the rename / deletion handling in the refresh workflow.

## Find affected summaries

For each changed file path, grep `.kb/summaries/` for references to it:

```bash
# One file
grep -rln "<changed-file-path>" .kb/summaries/

# Many files, batched. Reads each summary once, regardless of how many
# changed files it references.
grep -rln -F -f <(printf '%s\n' "<file1>" "<file2>" "<file3>") .kb/summaries/
```

The `-F` flag treats patterns as literal strings (avoids regex interpretation of `.` and `/`). The `-f` flag reads patterns from a file (here, a process substitution). The combination is the fast path for "find all summaries referencing any of these N files."

## Find affected indexes

Indexes mention summary names, not source file paths. After identifying affected summaries:

```bash
# affected_summaries = paths from the previous step
grep -rln -F -f <(printf '%s\n' "${affected_summaries[@]}") .kb/indexes/
```

Or, equivalently, scan all indexes once for any matching summary name.

## Detecting deletions referenced in `.kb/`

A hard flag: a summary references a file that no longer exists.

```bash
# For each deleted-file path (from --name-status above):
grep -l "<deleted-path>" .kb/summaries/ .kb/indexes/
```

If a match returns, the affected summary or index is broken until refreshed.

## Drift-report reuse (when `.kb/.drift-report.json` is present)

If a drift artifact exists and its `head_sha` matches the current HEAD and its `base_sha` matches the watermark, the refresh skill reuses the artifact's pre-computed file lists and skips both `git diff` and the `.kb/` greps. See the main SKILL.md step "Reuse drift artifact when available".

## Advancing state

After successful refresh:

```bash
HEAD_SHA=$(git -C <corpus-root> rev-parse HEAD)
NOW=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Then write .kb/.kb-state.json:
# {
#   "last_linted_sha": "<HEAD_SHA>",
#   "last_linted_at": "<NOW>",
#   "schema_version": 1
# }
```

Skip this step when invoked with `--no-advance-state` (the orchestrator wants to advance once at the end of a multi-refresh pass).
