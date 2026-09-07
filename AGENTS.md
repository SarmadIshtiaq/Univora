# AGENTS.md

Generic instructions for any AI coding agent (Cursor, Copilot, Codex, Aider, etc.) working in this
repository. If you are Claude specifically, also read `CLAUDE.md`.

## Read first
1. `architecture-essentials.md` — condensed architecture reference, read every session before coding.
2. `PRD.md` — product scope and requirements, read when a task touches scope or priority.
3. `Architecture.md` — full technical detail, read when you need the exact data model, the Stage 1
   consolidation plan, or the Phase 2 (outreach) module design.

## Non-negotiable project rules

1. **Evidence-only data (Phase 1) / grounded-only drafts (Phase 2).** Every record in every Phase 1
   output dataset must carry a real `source_url`. Every Phase 2 draft must carry `grounded_on`
   references to real Phase 1 records. Never fabricate, infer-and-fill, or hallucinate a value or a
   claim to complete a row or a sentence. Mark it `unresolved`/`review` instead.
2. **No LLM calls outside `agents/outreach/`.** University resolution, program discovery, faculty
   discovery, professor research, and requirements extraction are deterministic (requests +
   BeautifulSoup + rules). Do not introduce an LLM call into these paths. Phase 2 (`agents/outreach/`)
   is the one place an LLM (Claude API) is used, and only for drafting text grounded in Phase 1 data —
   never for extracting or verifying facts.
3. **CSV outputs are generated artifacts, not editable data files**, in both phases. Never hand-edit
   `data/processed/*.csv` directly to "fix" a row — fix the producing script and re-run, or add an
   override/review mechanism.
4. **Every stage is resumable.** Maintain a JSON registry (keyed by entity ID) alongside every CSV
   output, in both phases. Re-running a stage must not duplicate or corrupt previously verified
   (Phase 1) or approved/sent (Phase 2) rows.
5. **Respect target servers.** Keep existing timeouts/delays when scraping. Don't introduce
   unthrottled concurrency.
6. **Never send or submit anything automatically.** Phase 2 produces drafts only — no email is sent,
   no form is submitted, no application is filed by this system. That action is always manual.
7. **Don't expand scope silently.** `PRD.md` §5.3 defines what's explicitly out of scope (auto-send,
   school/professor ranking or recommendation, dashboard UI, non-USA universities). If a task implies
   building one of these, stop and confirm with the human first.

## Current pipeline status

| Stage | Status | Location |
|---|---|---|
| University resolution (Phase 1) | Built, needs consolidation | `agents/university/` |
| Program discovery (Phase 1) | Built | `agents/program/` |
| Faculty discovery (Phase 1) | Not built — critical path | `agents/faculty/` |
| Professor research (Phase 1) | Not built | `agents/research/` |
| Requirements + evidence (Phase 1) | Not built | `agents/requirements/` |
| Contact discovery (Phase 2) | Not built | `agents/outreach/contact/` |
| Outreach email + follow-up drafting (Phase 2) | Not built | `agents/outreach/email/` |
| CV/SOP tailoring (Phase 2) | Not built | `agents/outreach/docs/` |
| Outreach tracking (Phase 2) | Not built | `agents/outreach/tracker/` |

## Data model

See `Architecture.md` §4 for full pydantic model definitions, Phase 1 and Phase 2. Every entity
shares these trailing fields via `EvidenceBase`: `source_url`, `confidence`, `status`,
`agent_version`. Phase 2 draft models additionally carry `grounded_on`. New models should inherit
from `EvidenceBase` rather than redefining these.

## Definition of done

- Runs against real data in `data/processed/`.
- Produces both CSV (reviewable) and JSON registry (resumable state).
- No fabricated data (Phase 1) or ungrounded claims (Phase 2); uncertain results routed to a review
  file.
- Phase 2 output is always a draft — never sent/submitted.
- No new dependency added unless strictly necessary, keep `requirements.txt` minimal.
- Change is consistent with the pipeline pattern already established by Stage 1/Stage 2, unless the
  task is explicitly to change that pattern (and if so, `Architecture.md` should be updated too).
