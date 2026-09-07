# Univora — Architecture

> This document defines **how** Univora is built: tech stack, data models, pipeline design, and file
> layout. For **what** it does and **why**, see `PRD.md`. For a short-form version an agent should
> actually load into context while coding, see `architecture-essentials.md`.

---

## 1. Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.10+ | Existing codebase, good scraping/data ecosystem |
| HTTP | `requests` | Simple synchronous scraping, already used everywhere |
| HTML parsing | `beautifulsoup4` | Already used, sufficient for structured academic pages |
| Data validation | `pydantic` | Backs every data model in Section 4, both phases |
| Tabular data | `pandas` | Used by resolver/finalizer scripts for CSV I/O |
| Persistent state | Flat files: CSV (human-reviewable) + JSON registry (machine state) | No DB dependency, matches "no paid infra" principle |
| Orchestration | Plain CLI scripts (`argparse`) run manually or via `workflows/n8n/` | No task queue/scheduler yet |
| LLM usage (Phase 1) | **None.** Deterministic, reviewable, no API cost/rate limits | University/program/faculty/research/requirements agents |
| LLM usage (Phase 2 only) | Claude API (Anthropic), isolated to `agents/outreach/` | Drafting only — never used to invent facts, always grounded in Phase 1 CSVs passed in as context |

No database, no cloud infra is required to run the core pipeline. Phase 2's LLM usage is the one
deliberate, explicit exception to "no LLM," and it must stay contained to `agents/outreach/` — it is
never a dependency of Stage 1–5 discovery code.

## 2. High-Level Pipeline Architecture

```
PHASE 1 — Research (deterministic, no LLM)
University Resolution -> Program Discovery -> Faculty Discovery -> Professor Research -> Requirements
(agents/university)      (agents/program)      (agents/faculty)     (agents/research)   (agents/requirements)

PHASE 2 — Outreach (LLM-assisted, human-reviewed, grounded in Phase 1 output)
Contact Discovery -> Email Draft -> CV/SOP Tailoring -> Outreach Tracking -> Follow-up Draft
(agents/outreach/contact) (agents/outreach/email) (agents/outreach/docs) (agents/outreach/tracker) (agents/outreach/email)
```

Each Phase 1 stage:
- Reads the verified output of the previous stage (never re-derives it from scratch).
- Writes a CSV (reviewable) + a JSON registry (resumability / dedupe state).
- Marks failures/uncertainty explicitly rather than dropping or guessing.
- Uses no LLM.

Each Phase 2 stage:
- Reads verified Phase 1 CSVs (Faculty, ProfessorResearch, Requirements) as grounding context —
  never re-scrapes.
- Writes a CSV (reviewable) + a JSON registry, same pattern as Phase 1.
- Any LLM-generated content (email body, SOP paragraph) must be stored alongside the grounding
  record IDs it cites, so a human can verify "where did this claim come from."
- Never performs an irreversible action (no send, no submit) — output is always a draft.

## 3. Current Stage 1: University Resolution — NEEDS CONSOLIDATION

**Problem:** five scripts currently share responsibility for this stage with overlapping logic:

| Script | Actual responsibility today |
|---|---|
| `build_university_dataset.py` | Parses the raw QS rankings Excel file into `universities_usa.csv` (seed list) |
| `university_agent.py` | Reads `universities_usa.csv` + registry, produces/updates `university_sources.csv` |
| `university_resolver.py` | Single-university resolution: verified local list -> cache -> Wikidata |
| `bulk_university_resolver.py` | Batch version of resolution against `universities_usa.csv`, writes `university_sources.csv` |
| `finalize_university_agent.py` | Reconciles QS file + existing `university_sources.csv` into a finalized version |

**Target architecture (do this before building Stage 3):**

```
build_university_dataset.py   (seed: raw rankings -> universities_usa.csv)
        |
        v
university_resolver.py        (single canonical resolution module: verified list -> cache -> Wikidata)
        |
        v
bulk_university_resolver.py   (thin batch runner that CALLS university_resolver.py per row)
        |
        v
finalize_university_agent.py  (final reconciliation pass -> university_sources.csv)
```

`university_agent.py`'s responsibility should be folded into either the resolver or the finalizer —
it currently duplicates logic that already exists in the other two. **Decision needed**: pick one, do
not maintain three parallel "produce university_sources.csv" code paths. This consolidation is a
prerequisite task before Stage 3 (Faculty) is built, so faculty discovery has one trustworthy,
single-sourced input table.

## 4. Data Models

### 4.0 Shared base (all phases)
```python
class EvidenceBase(BaseModel):
    source_url: str | None       # required unless status == "unresolved"
    confidence: float            # 0.0-1.0
    status: str                  # "verified" | "review" | "unresolved"
    agent_version: str
```

### Phase 1 models (unchanged from prior version)

#### 4.1 University (universities_usa.csv -> university_sources.csv)
```python
class University(EvidenceBase):
    university_id: str          # e.g. "UNI-STANFORD-UNIVERSITY"
    university_name: str
    qs_rank_2027: int | None
    official_domain: str | None
    university_website: str | None
    discovery_method: str       # e.g. "existing_verified_output", "wikidata"
    wikidata_id: str | None
    website_status: str         # "not_checked" | "ok" | "error"
    discovery_status: str       # "success" | "unresolved" | "review"
```

#### 4.2 Program (programs.csv)
```python
class Program(EvidenceBase):
    program_id: str
    university_id: str          # FK -> University.university_id
    university_name: str
    school_name: str
    department_name: str
    program_name: str
    degree_level: str           # "PhD" | "Masters" | "Certificate" | ...
    degree_name: str
    program_url: str
    evidence: str                # short excerpt/snippet backing the extraction
```

#### 4.3 Faculty (Stage 3 — build next)
```python
class Faculty(EvidenceBase):
    faculty_id: str
    program_id: str              # FK -> Program.program_id
    university_id: str           # FK -> University.university_id
    full_name: str
    title: str                   # "Assistant Professor", etc.
    profile_url: str
    email: str | None            # if directly listed on faculty page; else Phase 2 contact-discovery fills it
```

#### 4.4 ProfessorResearch (Stage 4)
```python
class ProfessorResearch(EvidenceBase):
    research_id: str
    faculty_id: str               # FK -> Faculty.faculty_id
    research_areas: list[str]
    lab_name: str | None
    lab_url: str | None
    summary: str                  # short, extracted (not generated) description
```

#### 4.5 Requirement (Stage 5)
```python
class Requirement(EvidenceBase):
    requirement_id: str
    program_id: str                # FK -> Program.program_id
    requirement_type: str          # "GRE" | "TOEFL/IELTS" | "LOR" | "deadline" | "SOP" | ...
    value: str                     # free text or ISO date for deadlines
```

### Phase 2 models (new)

#### 4.6 Contact (agents/outreach/contact)
```python
class Contact(EvidenceBase):
    contact_id: str
    faculty_id: str                # FK -> Faculty.faculty_id
    email: str | None
    linkedin_url: str | None
    discovery_method: str          # "faculty_page" | "department_directory" | "manual_review"
```

#### 4.7 ApplicantProfile (agents/outreach, single user-maintained file, not scraped)
```python
class ApplicantProfile(BaseModel):
    full_name: str
    degree: str                    # e.g. "BSCS"
    gpa: float | None
    research_interests: list[str]
    projects: list[str]            # short descriptions, user-supplied
    publications: list[str]        # empty list if none yet
    github_url: str | None
    linkedin_url: str | None
    resume_source_path: str        # path to the user's actual CV, never fabricated content
```

#### 4.8 OutreachDraft (agents/outreach/email)
```python
class OutreachDraft(EvidenceBase):
    draft_id: str
    faculty_id: str                 # FK -> Faculty.faculty_id
    contact_id: str                 # FK -> Contact.contact_id
    grounded_on: list[str]          # ProfessorResearch.research_id list this draft cites
    subject: str
    body: str
    draft_type: str                 # "initial" | "follow_up"
    review_status: str              # "drafted" | "approved" | "sent" | "replied" | "no_response"
```

#### 4.9 DocumentDraft (agents/outreach/docs — CV/SOP tailoring)
```python
class DocumentDraft(EvidenceBase):
    doc_draft_id: str
    program_id: str                 # FK -> Program.program_id
    faculty_id: str | None          # FK -> Faculty.faculty_id, if professor-specific
    doc_type: str                   # "cv_bullets" | "sop_paragraph" | "motivation_letter"
    grounded_on: list[str]          # Program/Requirement/ProfessorResearch record IDs cited
    content: str
    review_status: str              # "drafted" | "approved" | "final"
```

Every Phase 1 model inherits `EvidenceBase`. Phase 2 models also inherit it — `source_url` for a
draft record means "the grounding data source," and `confidence` reflects how well the draft is
supported by verified data, not writing quality.

## 5. File & Folder Layout

```
Univora/
├── PRD.md
├── Architecture.md
├── architecture-essentials.md
├── CLAUDE.md
├── AGENTS.md
├── agents/
│   ├── university/       (Phase 1, Stage 1)
│   ├── program/           (Phase 1, Stage 2)
│   ├── faculty/            (Phase 1, Stage 3 — build next)
│   ├── research/           (Phase 1, Stage 4)
│   ├── requirements/       (Phase 1, Stage 5)
│   └── outreach/           (Phase 2 — new, LLM-using, isolated)
│       ├── contact/        (email/LinkedIn discovery)
│       ├── email/          (draft + follow-up generation)
│       ├── docs/            (CV/SOP tailoring)
│       └── tracker/        (outreach status tracking)
├── backend/                 (reserved for future API/service layer, empty today)
├── data/
│   ├── raw/                  (unmodified source inputs, incl. applicant_profile.yaml)
│   ├── processed/            (pipeline outputs: CSV + JSON registries, both phases)
│   └── external/             (third-party reference data)
├── workflows/
│   └── n8n/
├── tests/
└── docs/
```

## 6. Registry / Resumability Pattern

Every stage, in both phases, follows the same pattern, already established by
`program_discovery_registry.json` and `university_registry.json`:

- **Registry JSON** keyed by the entity's ID, storing: last-run status, last-run timestamp, agent
  version that produced it, and enough state to skip already-verified entities on re-run.
- **CSV output** is the human-reviewable, "current best known state" table — always fully rewritten
  from the registry, never hand-edited (hand edits go in a separate review/override file if needed).
- **Review CSV** (e.g. `program_discovery_review.csv`) holds anything below a confidence threshold or
  that failed discovery, for manual inspection — never silently dropped.

Phase 2's registries additionally store `review_status` transitions (e.g. `drafted` -> `approved`)
so re-running the drafting stage doesn't regenerate/overwrite a draft the user already approved or
marked sent.

## 7. Non-Goals (architectural)

- No database engine (Postgres/SQLite) in v1 — flat files are sufficient at this scale and keep the
  project zero-infrastructure to run.
- No async/concurrent scraping in v1 — keep it simple and polite to target servers; revisit only if
  runtime becomes a real bottleneck.
- **No LLM in Phase 1 discovery agents** (university/program/faculty/research/requirements). LLM
  usage is confined entirely to `agents/outreach/` (Phase 2).
- **No auto-send.** Phase 2 never calls an email-sending API, form-submission, or any other
  irreversible external action — every output is a draft file/message for the human to act on.
