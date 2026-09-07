# Univora — Architecture Essentials

> Condensed reference for a coding agent working in this repo. Full detail lives in `Architecture.md`;
> product intent lives in `PRD.md`. Read this file first, before touching code.

## Pipeline

```
PHASE 1 (no LLM, deterministic):
University -> Program -> Faculty -> Professor Research -> Requirements

PHASE 2 (LLM-assisted, isolated to agents/outreach/, human-reviewed, never auto-sends):
Contact discovery -> Outreach email draft -> CV/SOP tailoring -> Tracking -> Follow-up draft
```

Stage N reads Stage N-1's verified CSV output. Never re-derive earlier stages from scratch. Phase 2
reads Phase 1's verified CSVs as grounding — never re-scrapes, never invents facts not present there.

## Stack
- Python 3.10+, `requests`, `beautifulsoup4`, `pandas`, `pydantic`.
- **Phase 1: no LLM, no external paid API.** Deterministic scraping + extraction only.
- **Phase 2: Claude API allowed, but only inside `agents/outreach/`.** Never import an LLM client in
  university/program/faculty/research/requirements code.
- No database — flat files only: CSV (human-reviewable) + JSON registry (machine/resumability state),
  in both phases.

## Folder layout

```
agents/<stage>/        one folder per Phase 1 stage
agents/outreach/<sub>/  contact, email, docs, tracker — Phase 2 submodules
data/raw/               untouched source inputs (incl. applicant_profile.yaml)
data/processed/         pipeline outputs (CSV + JSON registries), source of truth, both phases
workflows/n8n/          optional orchestration
tests/                  mirrors agents/ structure
```

## Rules every agent/script must follow

1. **Evidence or nothing.** Every Phase 1 output row needs a `source_url`. Every Phase 2 draft needs
   `grounded_on` record IDs pointing at real Phase 1 rows. If it can't be verified/grounded, mark
   `status = "unresolved"` or `"review"` — never fabricate or guess a value, and never let the LLM
   invent a research interest, publication, or requirement that isn't in the data.
2. **Idempotent re-runs.** Re-running a stage on the same input must not duplicate or corrupt already
   `verified`/`approved`/`sent` rows in the registry.
3. **CSV + registry pair.** Every stage, both phases, writes both: a reviewable CSV and a JSON
   registry keyed by entity ID with last-run status/timestamp/agent_version.
4. **Shared schema fields.** Every entity model ends with: `source_url, confidence, status,
   agent_version` (`EvidenceBase`). Phase 2 drafts add `grounded_on` on top of this. Don't redefine
   these per model.
5. **Stage 1 (university resolution) is mid-consolidation.** There are currently 5 overlapping
   scripts (`build_university_dataset.py`, `university_agent.py`, `university_resolver.py`,
   `bulk_university_resolver.py`, `finalize_university_agent.py`). Target end-state:
   `build_university_dataset.py` (seed) -> `university_resolver.py` (single-entity resolution logic)
   -> `bulk_university_resolver.py` (thin batch runner calling the resolver) ->
   `finalize_university_agent.py` (final reconciliation). Do not add a 6th parallel path, consolidate
   into this shape when touching Stage 1 code.
6. **Be polite to target servers.** Keep existing request delays/timeouts; don't parallelize scraping
   without deliberate rate-limiting.
7. **Phase 2 never sends or submits anything.** Email drafts, follow-ups, and document drafts are
   always written to file/CSV for human review. No SMTP call, no form auto-submit, ever.
8. **Phase 2 LLM calls must pass grounding context explicitly**, i.e. the actual Faculty +
   ProfessorResearch (+ Requirement, + ApplicantProfile) rows relevant to that draft — never rely on
   the model's general/parametric knowledge of a professor or program.

## Current build status (check before assuming something exists)

- DONE: Stage 1 (University resolution), exists, needs consolidation (see rule 5).
- DONE: Stage 2 (Program discovery), exists in `agents/program/program_discovery_agent.py`.
- NOT BUILT: Stage 3 (Faculty discovery). Create real logic in `agents/faculty/` when starting this.
  **This is the critical-path blocker for everything downstream, including all of Phase 2.**
- NOT BUILT: Stage 4 (Professor research), `agents/research/`.
- NOT BUILT: Stage 5 (Requirements + evidence), `agents/requirements/`.
- NOT BUILT: Phase 2 (Outreach: contact discovery, email drafts, CV/SOP tailoring, tracking,
  follow-ups), `agents/outreach/`. Now committed v1 scope (previously mis-scoped as "future").
- `backend/` is an empty placeholder for a possible future API layer, do not assume any backend
  service exists yet.

## Data model quick reference

| Entity | Key fields beyond `EvidenceBase` | FK |
|---|---|---|
| University | `university_id`, `official_domain`, `discovery_method` | - |
| Program | `program_id`, `university_id`, `school_name`, `department_name`, `degree_level` | `university_id` |
| Faculty (new) | `faculty_id`, `program_id`, `full_name`, `title`, `profile_url` | `program_id` |
| ProfessorResearch (new) | `research_id`, `faculty_id`, `research_areas`, `lab_name` | `faculty_id` |
| Requirement (new) | `requirement_id`, `program_id`, `requirement_type`, `value` | `program_id` |
| Contact (Phase 2, new) | `contact_id`, `faculty_id`, `email`, `linkedin_url` | `faculty_id` |
| OutreachDraft (Phase 2, new) | `draft_id`, `faculty_id`, `contact_id`, `grounded_on`, `body`, `review_status` | `faculty_id`, `contact_id` |
| DocumentDraft (Phase 2, new) | `doc_draft_id`, `program_id`, `doc_type`, `grounded_on`, `content` | `program_id` |
| ApplicantProfile (Phase 2, new, not scraped) | `full_name`, `research_interests`, `projects`, `resume_source_path` | - |

## When in doubt

Re-read `PRD.md` §9 (Known Current State) and §10 (Open Questions) before making a design decision
that isn't covered here, don't silently invent new scope. Phase 2 is now in scope, but its shape
(exact CLI commands, exact prompt templates) is not yet fixed — treat those as implementation
decisions you can make within the schema above, not product decisions.
