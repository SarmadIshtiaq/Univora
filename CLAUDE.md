# CLAUDE.md

Instructions for Claude (Claude Code / any Claude-based coding agent) working in this repository.

## Before doing anything

Read, in this order:
1. `architecture-essentials.md` — always, every session. This is the fast-context version.
2. `PRD.md` — if the task touches scope, priorities, or "should we build X" decisions.
3. `Architecture.md` — only when you need full detail (data model definitions, the Stage 1
   consolidation plan, folder layout rationale) that isn't in the essentials file.

Do not start writing code before you've loaded `architecture-essentials.md` into context for the
session. It is short by design — there's no excuse to skip it.

## Ground rules specific to this project

- **This is a data-integrity-sensitive scraper/extraction pipeline, not a typical CRUD app.** The
  single most important invariant: no fact in any output file may exist without a `source_url`. If
  you write code that produces a record without a real source URL, that's a bug, not an edge case.
- **Don't call an LLM API from core pipeline code.** The existing agents are explicitly LLM-free. If a
  task seems to require an LLM (e.g. summarizing professor research), stop and flag it — it needs to
  be an isolated, explicitly-named module, not folded into the deterministic scrapers.
- **Stage 1 university-resolution scripts are messy on purpose (for now).** There are 5 scripts with
  overlapping responsibility. Don't "clean this up" as a side effect of an unrelated task. If your task
  IS the consolidation, follow the target shape in `architecture-essentials.md` rule 5 exactly.
- **Never hand-edit a CSV output file directly.** These are generated artifacts. If a row is wrong, fix
  the agent that produced it and re-run, or add to a review/override file, don't patch `programs.csv`
  by hand.
- **Preserve resumability.** Any new stage you build (faculty, research, requirements) must write a
  JSON registry keyed by entity ID, exactly like `program_discovery_registry.json` and
  `university_registry.json` already do. Look at those two files as the reference pattern before
  inventing a new one.

## Workflow expectations

- Before implementing a new stage (faculty/research/requirements), propose the pydantic model for it
  first (see `Architecture.md` Section 4 for the proposed shapes) and confirm it matches the shared
  `EvidenceBase` pattern before writing extraction logic.
- Prefer extending an existing agent file's pattern over introducing a new library, new async
  framework, or new state-storage mechanism. Consistency across stages matters more than any single
  stage being locally "better."
- When you finish a task, check it against `PRD.md` Section 6 (Functional Requirements table) and note
  if anything you built maps to an FR — helps keep the PRD accurate over time.
- If you find yourself needing to make a product decision (not a technical one) that isn't answered in
  `PRD.md`, stop and ask rather than assuming. Product decisions belong to the human; technical
  implementation decisions within the existing architecture are yours to make.

## What "done" looks like for a task in this repo

- Code runs against real data in `data/processed/`, not synthetic/mocked data, unless explicitly
  building a test.
- New/changed stage produces both a CSV and a registry JSON.
- Anything uncertain or unresolved is written to a review file, not dropped or guessed.
- No new top-level dependency added without checking it's really needed (`requirements.txt` should
  stay minimal — currently `requests`, `beautifulsoup4`, `pydantic`).
CLAUDEEOF