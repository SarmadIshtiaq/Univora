# AGENTS.md

Generic instructions for any AI coding agent (Cursor, Copilot, Codex, Aider, etc.) working in this
repository. If you are Claude specifically, also read `CLAUDE.md`.

## Read first
1. `architecture-essentials.md` — condensed architecture reference, read every session before coding.
2. `PRD.md` — product scope and requirements, read when a task touches scope or priority.
3. `Architecture.md` — full technical detail, read when you need the exact data model or the Stage 1
   consolidation plan.

## Non-negotiable project rules

1. **Evidence-only data.** Every record in every output dataset must carry a real `source_url`. Never
   fabricate, infer-and-fill, or hallucinate a value to complete a row. Mark it `unresolved`/`review`
   instead.
2. **No LLM calls in the core discovery pipeline.** University resolution, program discovery, faculty
   discovery, and requirements extraction are deterministic (requests + BeautifulSoup + rules). Do not
   introduce an LLM call into these paths. If a future feature genuinely needs one, it must live in its
   own clearly-named module and be optional.
3. **CSV outputs are generated artifacts, not editable data files.** Never hand-edit
   `data/processed/*.csv` directly to "fix" a row, fix the producing script and re-run, or add an
   override/review mechanism.
4. **Every stage is resumable.** Maintain a JSON registry (keyed by entity ID) alongside every CSV
   output. Re-running a stage must not duplicate or corrupt previously verified rows.
5. **Respect target servers.** Keep existing timeouts/delays when scraping. Don't introduce unthrottled
   concurrency.
6. **Don't expand scope silently.** `PRD.md` Section 5.2/5.3 define what's explicitly out of scope for
   now (application assistance, outreach automation, recommendations, non-USA universities). If a task
   implies building one of these, stop and confirm with the human first.

## Current pipeline status

| Stage | Status | Location |
|---|---|---|
| University resolution | Built, needs consolidation | `agents/university/` |
| Program discovery | Built | `agents/program/` |
| Faculty discovery | Not built | `agents/faculty/` |
| Professor research | Not built | `agents/research/` |
| Requirements + evidence | Not built | `agents/requirements/` |

## Data model

See `Architecture.md` Section 4 for full pydantic model definitions. Every entity shares these
trailing fields: `source_url`, `confidence`, `status`, `agent_version`. New models should inherit from
a shared `EvidenceBase` rather than redefining these.

## Definition of done

- Runs against real data in `data/processed/`.
- Produces both CSV (reviewable) and JSON registry (resumable state).
- No fabricated data; uncertain results routed to a review file.
- No new dependency added unless strictly necessary, keep `requirements.txt` minimal.
- Change is consistent with the pipeline pattern already established by Stage 1/Stage 2, unless the
  task is explicitly to change that pattern (and if so, `Architecture.md` should be updated too).