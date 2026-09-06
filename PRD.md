# Univora — Product Requirements Document (PRD)

> This document defines **what** Univora is, **who** it's for, and **what it must do**.
> It intentionally avoids tech stack, code structure, or implementation detail — that lives in `Architecture.md`.

---

## 1. Problem

Applying to graduate programs (especially research-based Masters/PhD in the US) requires manually
researching, per university:

- Which schools/departments offer relevant programs
- Which faculty work in a given research area
- What each professor is currently researching
- Admission requirements (GRE, deadlines, LORs, etc.)
- Evidence/links backing all of the above, so claims can be verified

Doing this by hand across 50–200 universities is repetitive, slow, and error-prone. Information is
scattered across university sites, department pages, and faculty pages, each with different structure.

## 2. Who this is for

- **Primary user (v1): the builder themself** — a prospective grad-school applicant who wants a
  structured, evidence-backed research base instead of scattered browser tabs and notes.
- Future users: other applicants who want the same research assistance, self-hosted or shared.

## 3. Product Principle

> **Human chooses. AI researches. Automation handles repetitive work.**

The system does not decide *for* the user (which school, which professor, whether to apply). It
gathers verifiable evidence and structures it so the human can decide faster and with less manual work.

## 4. Core Pipeline (what the product does, end to end)

University → Programs → Faculty → Professor Research → Requirements → Evidence

Each stage should be independently runnable and independently resumable — a partial run of stage 2
should not require re-running stage 1.

## 5. Scope

### 5.1 In scope for v1
- **University discovery**: resolve a starting list of universities (currently QS-ranked USA
  universities) to verified official domains.
- **Program discovery**: for each university, find real academic programs (school → department →
  program → degree) sourced only from the university's own official domain.
- **Faculty discovery**: for each relevant program/department, find faculty members.
- **Professor research extraction**: for each faculty member, extract their current research
  focus/areas.
- **Requirements extraction**: extract program admission requirements (tests, deadlines, materials).
- **Evidence collection**: every extracted fact must be traceable to a source URL. No fact should
  exist in the dataset without a `source_url` / evidence trail.

### 5.2 Explicitly out of scope for v1
- Application assistance (SOP/CV/email generation)
- Outreach tracking or automated emailing
- Recommendation or ranking of "best fit" schools
- Any UI/dashboard beyond CSV/JSON outputs and CLI usage
- Non-USA universities (may be revisited later)

### 5.3 Future scope (not v1, do not build yet)
- Application assistance (CV, SOP, outreach email drafting)
- Outreach tracking and follow-up automation
- Research-fit matching between the user's interests and professor research
- Feedback-driven re-prioritization based on user decisions

## 6. Functional Requirements

| # | Requirement | Notes |
|---|---|---|
| FR1 | Given a ranked list of universities, produce a verified official domain per university | Existing: `university_sources.csv` |
| FR2 | Given a verified university domain, discover real academic programs on that domain only | No guessing, no third-party aggregator data |
| FR3 | Every discovered program must include: university, school/department, program name, degree level, source URL, confidence, status | Matches existing `programs.csv` schema |
| FR4 | Every pipeline stage must be resumable / re-runnable without duplicating existing verified records | Registry/cache files already used for this |
| FR5 | Every stage must produce a human-reviewable output (CSV) plus a machine state file (JSON registry) | Existing pattern, keep consistent |
| FR6 | Failed/uncertain discoveries must be flagged for manual review, not silently dropped or silently guessed | e.g. `program_discovery_review.csv` |
| FR7 | No fabricated data. If a fact cannot be found with evidence, it is marked missing/unresolved, not filled in | Non-negotiable data integrity rule |

## 7. Non-Functional Requirements

- **No paid/LLM APIs required for core pipeline** (current agents explicitly avoid LLM calls — keep
  this constraint unless a future version deliberately changes it in `Architecture.md`).
- **Idempotency**: re-running a stage on the same input should not corrupt or duplicate prior verified
  output.
- **Respect target sites**: reasonable request delays/timeouts (already present as `REQUEST_DELAY`,
  `REQUEST_TIMEOUT`) — this is a scraping-adjacent system and must not hammer university servers.
- **Traceability**: every row in every output dataset must be attributable to a discovery method and,
  where applicable, a source URL.

## 8. Success Criteria (v1)

- [ ] For a batch of USA universities, ≥90% resolve to a verified official domain with high confidence.
- [ ] For universities with a verified domain, program discovery produces at least one correctly
      attributed program with a valid source URL, for the majority of universities attempted.
- [ ] Faculty and professor-research stages exist and produce evidence-backed records for at least a
      pilot subset of universities/programs (this is the current frontier of the project).
- [ ] Every output file conforms to a single, consistent schema (see `Architecture.md`).
- [ ] Re-running any stage does not duplicate or corrupt previously verified records.

## 9. Known Current State (honest assessment, as of this doc)

- University discovery and program discovery pipelines exist and run.
- There are multiple overlapping university-resolution scripts (`university_agent.py`,
  `university_resolver.py`, `bulk_university_resolver.py`, `finalize_university_agent.py`,
  `build_university_dataset.py`) whose responsibilities overlap and are not clearly separated.
  **Architecture.md must resolve this into one clear pipeline before further stages are built.**
- Faculty discovery, professor research extraction, and requirements extraction are **not yet
  implemented** — only stubbed as folders/scope. These are the next things to build, and should follow
  the same evidence-based, no-LLM-by-default pattern as the existing agents.

## 10. Open Questions (resolve before/while building faculty stage)

1. Do we standardize on a single "university resolver" script going forward, and deprecate the others?
2. What is the canonical `program_id` / `faculty_id` ID scheme so faculty rows can join back to programs?
3. How do we handle universities with no discoverable faculty listing page (common for large schools
   with department-siloed sites)?
PRDEOF