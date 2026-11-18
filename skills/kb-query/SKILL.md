---
name: kb-query
description: Use when answering a question against a .kb/ knowledge base. Enforces indexes-first navigation — reads _root.md, picks area indexes, descends to summaries. Triggers on "query the kb", "ask the knowledge base", "найди в kb", "спроси базу знаний".
---

# kb-query — Answer via Progressive Disclosure

## When to use

User asks a question about a corpus that has a `.kb/` directory. The knowledge base exists — you're reading it, not building it.

If `.kb/` does not exist, suggest `/kb-build` and stop.

## Input

- **Question** — natural language, from the user.

## Workflow (strict order)

### 1. Read `_root.md` first

Open `.kb/indexes/_root.md`. Always. No exceptions on first access to the KB.

This is the indexes-first rule. It's cheap (≤300 tokens) and orients you correctly in one hop. Skipping it to "save time" costs more time when you pick the wrong summaries.

### 2. Pick 1–3 area indexes

Based on `_root.md`, identify which areas are relevant to the question. Read those area indexes (`.kb/indexes/<area>.md`).

Typical count: 1 for focused questions, 2–3 for questions that cross domains. More than 3 means either the question is too broad or the areas are over-segmented.

### 3. Descend to summaries

From the area indexes, pick the specific leaf summaries to read. Read them.

### 4. Follow warm references freely

Once inside a summary, you may follow direct references to other summaries without returning to the index level. This relaxation is intentional — see [docs/navigation-rules.md](https://github.com/olegvg/olegvg-skills/blob/master/docs/navigation-rules.md). The indexes earn their keep on cold start; warm references are cheap.

### 4a. Surface decisions for the current summary

After reading a summary, also check whether any decision records reference it. Decisions live in `.kb/decisions/<YYYY-MM-slug>.md`; each record's `## Affected areas` block names the summaries it shapes. The lookup is one grep:

```bash
grep -l "<path-to-current-summary>" .kb/decisions/
```

Read whichever records the grep returns. **Do not** look for a `## Key decisions` section inside the summary — the linkage lives in the decision record, not in the summary. Decisions are immutable history; summaries describe the present.

For questions of the form "how does X work now, and why was it built that way?" — read the summary for X, then the decisions returned by the grep above. Both halves of the answer live along one navigation path.

### Direct mode: `--decisions-for <summary-path>` (no question)

If the user invokes the skill with a literal `--decisions-for <summary-path>` (or the equivalent natural-language form: "what decisions shaped `<summary-path>`?"), skip steps 1–4 and run the grep against `.kb/decisions/` directly:

```bash
grep -l "<summary-path>" .kb/decisions/ | xargs -I {} sh -c 'echo "## {}"; cat {}'
```

This is the explicit form of step 4a — a one-shot lookup with no indexes-first read. Print or summarize the matching records in order of filename (newest YYYY-MM first). If grep returns nothing, say so: "no decisions reference `<summary-path>` yet" is a valid answer.

### 5. Answer

Answer the question using what you read. Cite sources (file paths, line numbers) from the summaries. If the summaries point at code or docs in the corpus, you may open those sources — but only after the summary has pointed you there.

## Discipline

- **Always `_root.md` first on cold start.** Observable in traces. If you skipped it, you broke the pattern.
- **Bounded summary reads.** If you find yourself wanting to open 5+ summaries, stop. Either the question is too broad (ask the user to narrow) or an index is pointing at too many leaves (refresh candidate).
- **If nothing matches, say so.** Don't hallucinate an answer. "The KB has no coverage for this — the answer isn't here" is valid.

## When to suggest refresh

If during a query you discover:
- A summary references a file that no longer exists.
- An index points at a summary that's missing.
- The content in a summary contradicts what's in the sources.

...suggest `/kb-check-drift` to the user before trusting the answer.

## References

- Navigation rules: [docs/navigation-rules.md](https://github.com/olegvg/olegvg-skills/blob/master/docs/navigation-rules.md)
- Drift check: `kb-check-drift` (install separately when needed)
