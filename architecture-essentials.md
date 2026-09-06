# Univora — Architecture Essentials

> Condensed reference for a coding agent working in this repo. Full detail lives in `Architecture.md`;
> product intent lives in `PRD.md`. Read this file first, before touching code.

## Pipeline

University -> Program -> Faculty -> Professor Research -> Requirements -> Evidence

Stage N reads Stage N-1's verified CSV output. Never re-derive earlier stages from scratch.

## Stack
- Python 3.10+, `requests`, `beautifulsoup4`, `pandas`, `pydantic`.
- **No LLM, no external paid API in the core pipeline.** Deterministic scraping + extraction only.
- No database — flat files only: CSV (human-reviewable) + JSON registry (machine/resumability state).

## Folder layout

agents/<stage>/ one folder per pipeline stage
data/raw/ untouched source inputs
data/processed/ pipeline outputs (CSV + JSON registries), source of truth
workflows/n8n/ optional orchestration
tests/ mirrors agents/ structure


## Rules every agent/script must follow
1. **Evidence or nothing.** Every output row needs a `source_url`. If it can't be verified, mark
   `status = "unresolved"` or `"review"` — never fabricate or guess a value.
2. **Idempotent re-runs.** Re-running a stage on the same input must not duplicate or corrupt already
   `verified` rows in the registry.
3. **CSV + registry pair.** Every stage writes both: a reviewable CSV and a JSON registry keyed by
   entity ID with last-run status/timestamp/agent_version.
4. **Shared schema fields.** Every entity model ends with: `source_url, confidence, status,
   agent_version`. Use a shared base pydantic model (`EvidenceBase`), don't redefine these per model.
5. **Stage 1 (university resolution) is mid-consolidation.** There are currently 5 overlapping
   scripts (`build_university_dataset.py`, `university_agent.py`, `university_resolver.py`,
   `bulk_university_resolver.py`, `finalize_university_agent.py`). Target end-state:
   `build_university_dataset.py` (seed) -> `university_resolver.py` (single-entity resolution logic)
   -> `bulk_university_resolver.py` (thin batch runner calling the resolver) ->
   `finalize_university_agent.py` (final reconciliation). Do not add a 6th parallel path, consolidate
   into this shape when touching Stage 1 code.
6. **Be polite to target servers.** Keep existing request delays/timeouts; don't parallelize scraping
   without deliberate rate-limiting.

## Current build status (check before assuming something exists)
- DONE: Stage 1 (University resolution), exists, needs consolidation (see rule 5).
- DONE: Stage 2 (Program discovery), exists in `agents/program/program_discovery_agent.py`.
- NOT BUILT: Stage 3 (Faculty discovery). Create real logic in `agents/faculty/` when starting this.
- NOT BUILT: Stage 4 (Professor research), `agents/research/`.
- NOT BUILT: Stage 5 (Requirements + evidence), `agents/requirements/`.
- `backend/` is an empty placeholder for a possible future API layer, do not assume any backend
  service exists yet.

## Data model quick reference
| Entity | Key fields beyond the shared base | FK |
|---|---|---|
| University | `university_id`, `official_domain`, `discovery_method` | - |
| Program | `program_id`, `university_id`, `school_name`, `department_name`, `degree_level` | `university_id` |
| Faculty (new) | `faculty_id`, `program_id`, `full_name`, `title`, `profile_url` | `program_id` |
| ProfessorResearch (new) | `research_id`, `faculty_id`, `research_areas`, `summary` | `faculty_id` |
| Requirement (new) | `requirement_id`, `program_id`, `requirement_type`, `value` | `program_id` |

## When in doubt
Re-read `PRD.md` Section 9 (Known Current State) and Section 10 (Open Questions) before making a
design decision that isn't covered here, don't silently invent new scope.