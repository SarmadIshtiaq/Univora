# Univora — Product Requirements Document (PRD)

> This document defines **what** Univora is, **who** it's for, and **what it must do**.
> It intentionally avoids tech stack, code structure, or implementation detail — that lives in `Architecture.md`.

---

## 1. Problem

Applying to graduate programs (especially direct BS→PhD in the US) requires manually, per university:

- Finding which schools/departments offer relevant programs
- Finding which faculty work in a given research area
- Reading what each professor is currently researching (labs, recent publications)
- Finding a way to reach that professor (email, LinkedIn) and admission requirements
- Drafting a personalized outreach email per professor, and a CV/SOP tailored to that program

...across 184 QS-ranked US universities. Doing this by hand is repetitive, slow, and error-prone.
Information is scattered across university sites, department pages, faculty pages, and publication
indexes, each with different structure — and even once found, turning it into a good email or SOP
paragraph is itself slow, repeated work per professor.

## 2. Who this is for

- **Primary user (v1): the builder themself** — a direct BS→PhD applicant applying across ~184
  universities under a tight deadline, who wants a structured, evidence-backed research base AND
  ready-to-review outreach drafts, instead of scattered browser tabs, manual searches, and writing
  every email from scratch.
- Future users: other applicants who want the same assistance, self-hosted or shared.

## 3. Product Principle

> **Human chooses. AI researches and drafts. Automation handles repetitive work. Nothing is sent
> without the human reviewing it first.**

The system does not decide *for* the user (which school, which professor, whether to apply, whether
to send an email). It gathers verifiable evidence, structures it, and produces reviewable drafts so
the human can decide and act faster with far less manual work. No email is ever auto-sent; no fact is
ever fabricated.

## 4. Core Pipeline (what the product does, end to end)

**Phase 1 — Research pipeline (deterministic, evidence-only):**
University → Programs → Faculty → Professor Research → Requirements → Evidence

**Phase 2 — Outreach pipeline (LLM-assisted, grounded in Phase 1 evidence, human-reviewed):**
Faculty + Research (verified) → Contact discovery (email/LinkedIn) → Draft outreach email →
Tailored CV/SOP content → Outreach tracking → Follow-up drafts

Each stage in both phases should be independently runnable and independently resumable — a partial
run of a later stage should not require re-running an earlier one, and Phase 2 should never need to
re-scrape what Phase 1 already verified.

## 5. Scope

### 5.1 In scope for v1 (Phase 1 — Research pipeline)
- **University discovery**: resolve the starting list of 184 QS-ranked USA universities to verified
  official domains.
- **Program discovery**: for each university, find real academic programs (school → department →
  program → degree) sourced only from the university's own official domain.
- **Faculty discovery**: for each relevant program/department, find faculty members.
- **Professor research extraction**: for each faculty member, extract their current research
  focus/areas (and lab name/URL where discoverable).
- **Requirements extraction**: extract program admission requirements (tests, deadlines, materials).
- **Evidence collection**: every extracted fact must be traceable to a source URL. No fact should
  exist in the dataset without a `source_url` / evidence trail.

### 5.2 In scope for v1 (Phase 2 — Outreach pipeline)
Phase 2 is now committed scope for v1, not deferred — it is the reason the project exists. It is
built as an **isolated, LLM-using module** that only ever reads Phase 1's verified CSVs; it never
scrapes or fabricates faculty/research facts itself.

- **Contact discovery**: find a faculty member's email and LinkedIn profile, evidence-linked like
  everything else (`source_url` required, or `status = unresolved`).
- **Outreach email drafting**: one draft per verified faculty record, grounded only in that
  professor's `ProfessorResearch` row(s) — never invents research interests not present in the data.
- **CV / SOP tailoring**: program-specific CV bullet ordering / SOP paragraph content, grounded in
  the applicant's own supplied background (see §5.4) and the target program/professor's verified data.
- **Outreach tracking**: status per faculty contact (`not_contacted` / `drafted` / `sent` /
  `replied` / `no_response`), updated by the human, never auto-advanced by the system sending
  anything.
- **Follow-up drafting**: shorter follow-up draft for contacts marked `sent` with no reply after a
  user-specified interval.

### 5.3 Explicitly out of scope for v1
- **Sending anything automatically.** All emails, forms, and applications are drafted for the human
  to review and send/submit themselves. No SMTP, no auto-submit, ever.
- Recommendation or ranking of "best fit" schools/professors (the system surfaces evidence; the human
  judges fit).
- Any UI/dashboard beyond CSV/JSON outputs, CLI usage, and chat-based drafting (Claude/PhD Pipeline
  skill) for now — a dashboard is future scope.
- Non-USA universities (may be revisited later).

### 5.4 Applicant profile (required input for Phase 2, not fabricated by the system)
Phase 2 drafting stages need a small, explicit applicant-profile input file (background, GPA,
projects/publications if any, target research interests). This is supplied by the user once and
referenced by every draft — the system never invents applicant background to fill a gap.

## 6. Functional Requirements

| # | Requirement | Notes |
|---|---|---|
| FR1 | Given a ranked list of universities, produce a verified official domain per university | Existing: `university_sources.csv` |
| FR2 | Given a verified university domain, discover real academic programs on that domain only | No guessing, no third-party aggregator data |
| FR3 | Every discovered program must include: university, school/department, program name, degree level, source URL, confidence, status | Matches existing `programs.csv` schema |
| FR4 | Every pipeline stage (Phase 1 and Phase 2) must be resumable / re-runnable without duplicating existing verified records | Registry/cache files already used for this |
| FR5 | Every stage must produce a human-reviewable output (CSV) plus a machine state file (JSON registry) | Existing pattern, keep consistent |
| FR6 | Failed/uncertain discoveries must be flagged for manual review, not silently dropped or silently guessed | e.g. `program_discovery_review.csv` |
| FR7 | No fabricated data anywhere in Phase 1 or Phase 2. If a fact cannot be found with evidence, it is marked missing/unresolved, not filled in | Non-negotiable data integrity rule, applies to research facts (Phase 1) AND to claims made in drafts (Phase 2) |
| FR8 | Contact discovery must produce a `source_url` (or `status=unresolved`) for every email/LinkedIn found | Phase 2 |
| FR9 | Every outreach email/follow-up draft must cite which `Faculty`/`ProfessorResearch` record(s) it is grounded in | Phase 2, enables auditing "did the AI make this up" |
| FR10 | No email, form, or application is ever sent/submitted automatically by the system | Non-negotiable, Phase 2 |
| FR11 | CV/SOP tailoring must be traceable to (a) the applicant's own supplied profile and (b) the target program/professor's verified record — never a generic template presented as tailored | Phase 2 |
| FR12 | Outreach tracker status changes are user-driven (manual mark as sent/replied), not inferred by the system | Phase 2 |

## 7. Non-Functional Requirements

- **No paid/LLM APIs in Phase 1 (core discovery pipeline)** — kept fully deterministic, unchanged.
- **Phase 2 may use an LLM (Claude API)**, but only inside `agents/outreach/`, never inside
  university/program/faculty/research/requirements agents.
- **Idempotency**: re-running any stage on the same input should not corrupt or duplicate prior
  verified output, in either phase.
- **Respect target sites**: reasonable request delays/timeouts (already present as `REQUEST_DELAY`,
  `REQUEST_TIMEOUT`) — this is a scraping-adjacent system and must not hammer university servers.
- **Traceability**: every row in every output dataset, and every draft produced, must be attributable
  to a discovery method and, where applicable, a source URL or grounding record.

## 8. Success Criteria (v1)

- [ ] For a batch of USA universities, ≥90% resolve to a verified official domain with high confidence.
- [ ] For universities with a verified domain, program discovery produces at least one correctly
      attributed program with a valid source URL, for the majority of universities attempted.
- [ ] Faculty and professor-research stages produce evidence-backed records for at least a pilot
      subset of universities/programs.
- [ ] For faculty with verified research records, contact discovery resolves an email or LinkedIn for
      a majority, with the rest correctly marked `unresolved`.
- [ ] Every faculty with a resolved contact gets a reviewable outreach draft citing its grounding
      record(s).
- [ ] Every output file (Phase 1 and Phase 2) conforms to a single, consistent schema (see
      `Architecture.md`).
- [ ] Re-running any stage does not duplicate or corrupt previously verified records.

## 9. Known Current State (honest assessment, as of this doc)

- University discovery and program discovery pipelines exist and run (Phase 1, Stage 1–2).
- There are multiple overlapping university-resolution scripts (`university_agent.py`,
  `university_resolver.py`, `bulk_university_resolver.py`, `finalize_university_agent.py`,
  `build_university_dataset.py`) whose responsibilities overlap and are not clearly separated.
  **Architecture.md must resolve this into one clear pipeline; do this before building Stage 3.**
- Faculty discovery, professor research extraction, and requirements extraction (Phase 1, Stage
  3–5) are **not yet implemented** — only stubbed as folders/scope. These are the next things to
  build, and should follow the same evidence-based, no-LLM-by-default pattern as the existing agents.
  **Faculty (Stage 3) is the critical-path blocker** — Research, Requirements, and all of Phase 2
  depend on it.
- Phase 2 (Outreach) is **not yet implemented** — `agents/outreach/` exists as an empty folder. It
  was previously mis-scoped as "future, do not build"; this revision makes it committed v1 scope,
  since it is the primary reason the project was started.

## 10. Open Questions (resolve before/while building each stage)

1. Do we standardize on a single "university resolver" script going forward, and deprecate the others?
2. What is the canonical `program_id` / `faculty_id` ID scheme so faculty rows can join back to programs?
3. How do we handle universities with no discoverable faculty listing page (common for large schools
   with department-siloed sites)?
4. Where does the applicant-profile input (§5.4) live and in what format — a single YAML/JSON the
   user maintains, referenced by every Phase 2 draft?
5. What email-finding method(s) are acceptable for contact discovery (university directory pages,
   department pages) vs. out of bounds (paid people-search APIs, scraping non-official sources)?
