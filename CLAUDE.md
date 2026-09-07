# CLAUDE.md

Instructions for Claude (Claude Code / any Claude-based coding agent) working in this repository.

## Before doing anything

Read, in this order:
1. `architecture-essentials.md` — always, every session. This is the fast-context version.
2. `PRD.md` — if the task touches scope, priorities, or "should we build X" decisions.
3. `Architecture.md` — only when you need full detail (data model definitions, the Stage 1
   consolidation plan, Phase 2 module design) that isn't in the essentials file.

Do not start writing code before you've loaded `architecture-essentials.md` into context for the
session. It is short by design — there's no excuse to skip it.

## Ground rules specific to this project

- **This is a data-integrity-sensitive scraper/extraction pipeline plus a grounded-drafting layer,
  not a typical CRUD app.** The single most important invariant: no fact in any Phase 1 output file
  may exist without a `source_url`, and no claim in any Phase 2 draft may exist without a
  `grounded_on` reference to a real Phase 1 record. If you write code that produces a record or a
  draft sentence without real backing, that's a bug, not an edge case.
- **LLM calls are allowed ONLY inside `agents/outreach/`.** University, program, faculty, research,
  and requirements agents stay LLM-free — deterministic, reviewable, no API cost/rate limits. If a
  task outside `agents/outreach/` seems to require an LLM, stop and flag it; it does not belong there.
- **Inside `agents/outreach/`, every LLM call must be passed explicit grounding context** — the real
  Faculty/ProfessorResearch/Requirement/ApplicantProfile rows for that draft — never left to the
  model's general knowledge of a professor or program. Prompts should explicitly instruct the model
  not to add facts beyond what's provided.
- **Never auto-send.** No code in this repo may call an email-sending API, submit a form, or take any
  other irreversible external action on the user's behalf. Every Phase 2 output is a draft file for
  the human to review and act on manually.
- **Stage 1 university-resolution scripts are messy on purpose (for now).** There are 5 scripts with
  overlapping responsibility. Don't "clean this up" as a side effect of an unrelated task. If your task
  IS the consolidation, follow the target shape in `architecture-essentials.md` rule 5 exactly.
- **Never hand-edit a CSV output file directly.** These are generated artifacts, in both phases. If a
  row is wrong, fix the agent that produced it and re-run, or add to a review/override file, don't
  patch `programs.csv` (or any Phase 2 CSV) by hand.
- **Preserve resumability.** Any new stage you build (faculty, research, requirements, or any
  `agents/outreach/` submodule) must write a JSON registry keyed by entity ID, exactly like
  `program_discovery_registry.json` and `university_registry.json` already do. Look at those two
  files as the reference pattern before inventing a new one. Phase 2 registries additionally track
  `review_status` so re-runs don't clobber a draft the user already approved/sent.

## Workflow expectations

- Before implementing a new stage (faculty/research/requirements, or any outreach submodule),
  propose the pydantic model for it first (see `Architecture.md` §4 for the exact shapes) and confirm
  it matches the shared `EvidenceBase` pattern before writing extraction/drafting logic.
- Prefer extending an existing agent file's pattern over introducing a new library, new async
  framework, or new state-storage mechanism. Consistency across stages matters more than any single
  stage being locally "better."
- When you finish a task, check it against `PRD.md` §6 (Functional Requirements table) and note if
  anything you built maps to an FR — helps keep the PRD accurate over time.
- If you find yourself needing to make a product decision (not a technical one) that isn't answered
  in `PRD.md` — including anything that would expand scope beyond §5.1/§5.2 (e.g. adding
  auto-send, adding a ranking/recommendation feature) — stop and ask rather than assuming. Product
  decisions belong to the human; technical implementation decisions within the existing architecture
  are yours to make.

## What "done" looks like for a task in this repo

- Code runs against real data in `data/processed/`, not synthetic/mocked data, unless explicitly
  building a test.
- New/changed stage produces both a CSV and a registry JSON.
- Anything uncertain or unresolved (Phase 1) or ungrounded (Phase 2) is written to a review file, not
  dropped or guessed.
- No new top-level dependency added without checking it's really needed (`requirements.txt` should
  stay minimal — currently `requests`, `beautifulsoup4`, `pydantic`, plus the Anthropic SDK for
  `agents/outreach/` only).
