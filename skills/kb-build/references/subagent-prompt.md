# Subagent Prompt Shape (Pass 2)

In Pass 2, the main agent dispatches one subagent per semantic domain via the Task tool. Each subagent starts with a fresh context, sees only its slice of the corpus, and returns a short brief.

Use this as a starting point; adapt wording but **preserve the contract** (what the subagent reads, what it writes, what it returns).

## The prompt

```
Domain: <area-slug>

Files in this domain:
  - <path/to/file1>
  - <path/to/file2>
  - <path/to/file3>
  - ...

Your task:
  1. Read the listed files. Read them fully — that is the point of this pass.
  2. Write .kb/summaries/<area-slug>/overview.md — orientation for the domain.
     One paragraph of context, then how the pieces fit together. Optional
     Mermaid diagram.
  3. Write one leaf file per distinct topic at
     .kb/summaries/<area-slug>/<topic>.md. Topics within the domain that
     warrant their own file: distinct subsystems, distinct data shapes,
     distinct lifecycles.
  4. Follow templates/summary.template.md for file shape. Reference source
     code by symbol name in prose (`run_analysis`, `BillingService`);
     pin line numbers only in `## References` at the end (see
     docs/concept.md "Summary stability contract").
  5. Return a brief, max 200 words: area name, list of leaf files
     created, one-line description of each leaf. The main agent uses
     this brief to write the area index in Pass 3.

Rules:
  - One topic per leaf file. If you start a section that would be a
    second topic, that is a new leaf, not a section.
  - Prose, not bullet dumps. Concrete: name real symbols, describe
    real flows.
  - Mermaid where a diagram beats prose. Sparingly.
  - Do NOT write to .kb/indexes/. The main agent handles indexes in
    Pass 3 from your brief — your job is content, not navigation.
  - Do NOT read files outside your assigned list. If a referenced
    file lives in another domain, note it in the summary and let the
    main agent cross-link in Pass 3.
```

## Why this shape

- **"Read them fully"** — Pass 2 is the *only* pass that reads file bodies. The main agent has 5–10% of the corpus loaded from Pass 1 (headers) and only the briefs from Pass 2. Subagents read deeply on the main agent's behalf, and only their distilled brief flows back.
- **"One topic per leaf file"** — this is the contract every summary file must hold. A summary that mixes two topics fails progressive disclosure: the agent reads the whole file to learn either topic.
- **"Reference by symbol name"** — see [docs/concept.md "Summary stability contract"](../../../docs/concept.md). Refresh cost downstream depends on this.
- **"Max 200 words"** — the brief is what flows back into the main agent's context. Pass 3 writes N indexes from N briefs. If briefs run long, Pass 3 has to compress them anyway. Better to ask for compression up front.
- **"Do NOT write to indexes"** — indexes are a global concern. The main agent in Pass 3 has the whole brief set; subagents see only their slice. Subagents writing indexes would produce N inconsistent navigation surfaces.

## Parallelism

Dispatch subagents in parallel where the host environment supports it. Each subagent is independent — its inputs (file list) and outputs (summaries + brief) do not depend on other subagents. Parallelism is the difference between a build that takes minutes and one that takes an hour.

If the environment does not support subagents, fall back to iterative builds across separate sessions — one session per domain. Slower but produces the same artifacts.

## What the main agent does with the briefs

After Pass 2 completes, the main agent holds N briefs (one per domain). Pass 3 turns each brief into an `.kb/indexes/<area>.md` (300-token budget) and assembles `_root.md` from the area names. No file body is read in Pass 3. This is the context-window guarantee of the pattern.
