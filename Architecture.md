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
| Data validation | `pydantic` | Declared in `requirements.txt`; **currently underused** — should back the data models in Section 4 |
| Tabular data | `pandas` | Used by resolver/finalizer scripts for CSV I/O |
| Persistent state | Flat files: CSV (human-reviewable) + JSON registry (machine state) | No DB dependency, matches "no paid infra" principle |
| Orchestration | Plain CLI scripts (`argparse`) run manually or via `workflows/n8n/` | No task queue/scheduler yet |
| LLM usage | **None in core pipeline by design** (see PRD) | Deterministic, reviewable, no API cost/rate limits |

No database, no LLM API, no cloud infra is required to run the core pipeline today. If a future stage
(e.g. professor research summarization) needs an LLM, that must be an explicit, isolated, optional
component — not a dependency of the core discovery pipeline.

## 2. High-Level Pipeline Architecture

University Resolution -> Program Discovery -> Faculty Discovery -> Professor Research -> Requirements + Evidence
(agents/university) (agents/program) (NOT YET BUILT) (NOT YET BUILT) (NOT YET BUILT)


Each stage:
- Reads the verified output of the previous stage (never re-derives it from scratch).
- Writes a CSV (reviewable) + a JSON registry (resumability / dedupe state).
- Marks failures/uncertainty explicitly rather than dropping or guessing.

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

build_university_dataset.py (seed: raw rankings -> universities_usa.csv)
|
v
university_resolver.py (single canonical resolution module: verified list -> cache -> Wikidata)
|
v
bulk_university_resolver.py (thin batch runner that CALLS university_resolver.py per row)
|
v
finalize_university_agent.py (final reconciliation pass -> university_sources.csv)


`university_agent.py`'s responsibility should be folded into either the resolver or the finalizer —
it currently duplicates logic that already exists in the other two. **Decision needed**: pick one, do
not maintain three parallel "produce university_sources.csv" code paths. This consolidation is a
prerequisite task before Stage 3 (Faculty) is built, so faculty discovery has one trustworthy,
single-sourced input table.

## 4. Data Models

Use `pydantic` models mirroring these schemas so every stage validates its own output before writing
CSV/JSON. This directly implements PRD FR3 and FR7 (no fabricated/malformed data).

### 4.1 University (universities_usa.csv -> university_sources.csv)
```python
class University(BaseModel):
    university_id: str          # e.g. "UNI-STANFORD-UNIVERSITY"
    university_name: str
    qs_rank_2027: int | None
    official_domain: str | None
    university_website: str | None
    confidence: float           # 0.0-1.0
    discovery_method: str       # e.g. "existing_verified_output", "wikidata"
    wikidata_id: str | None
    website_status: str         # "not_checked" | "ok" | "error"
    discovery_status: str       # "success" | "unresolved" | "review"
```

### 4.2 Program (programs.csv)
```python
class Program(BaseModel):
    program_id: str
    university_id: str          # FK -> University.university_id
    university_name: str
    school_name: str
    department_name: str
    program_name: str
    degree_level: str           # "Masters" | "PhD" | "Certificate" | ...
    degree_name: str
    program_url: str
    source_url: str
    evidence: str                # short excerpt/snippet backing the extraction
    confidence: float
    status: str                  # "verified" | "review" | "unresolved"
    agent_version: str
```

### 4.3 Faculty (not yet implemented — proposed schema, keep this exact shape)
```python
class Faculty(BaseModel):
    faculty_id: str
    program_id: str              # FK -> Program.program_id
    university_id: str           # FK -> University.university_id
    full_name: str
    title: str                   # "Assistant Professor", etc.
    profile_url: str
    email: str | None
    source_url: str
    confidence: float
    status: str
    agent_version: str
```

### 4.4 ProfessorResearch (not yet implemented — proposed schema)
```python
class ProfessorResearch(BaseModel):
    research_id: str
    faculty_id: str               # FK -> Faculty.faculty_id
    research_areas: list[str]
    summary: str                  # short, extracted (not generated) description
    source_url: str
    confidence: float
    status: str
    agent_version: str
```

### 4.5 Requirement (not yet implemented — proposed schema)
```python
class Requirement(BaseModel):
    requirement_id: str
    program_id: str                # FK -> Program.program_id
    requirement_type: str          # "GRE" | "TOEFL/IELTS" | "LOR" | "deadline" | "SOP" | ...
    value: str                     # free text or ISO date for deadlines
    source_url: str
    confidence: float
    status: str
    agent_version: str
```

Every model above shares the same closing fields (`source_url`, `confidence`, `status`,
`agent_version`) — this is intentional and should be factored into a shared `EvidenceBase` pydantic
model that all five inherit from, to enforce the PRD's evidence-traceability requirement uniformly.

## 5. File & Folder Layout

Univora/
├── PRD.md
├── Architecture.md
├── architecture-essentials.md
├── CLAUDE.md
├── AGENTS.md
├── agents/
│ ├── university/ (Stage 1)
│ ├── program/ (Stage 2)
│ ├── faculty/ (Stage 3, new, currently empty)
│ ├── research/ (Stage 4, new, currently empty)
│ └── requirements/ (Stage 5, new, currently empty)
├── backend/ (reserved for future API/service layer, empty today)
├── data/
│ ├── raw/ (unmodified source inputs)
│ ├── processed/ (pipeline outputs: CSV + JSON registries)
│ └── external/ (third-party reference data)
├── workflows/
│ └── n8n/
├── tests/
└── docs/


## 6. Registry / Resumability Pattern

Every stage follows the same pattern, already established by `program_discovery_registry.json` and
`university_registry.json`:

- **Registry JSON** keyed by the entity's ID, storing: last-run status, last-run timestamp, agent
  version that produced it, and enough state to skip already-verified entities on re-run.
- **CSV output** is the human-reviewable, "current best known state" table — always fully rewritten
  from the registry, never hand-edited (hand edits go in a separate review/override file if needed).
- **Review CSV** (e.g. `program_discovery_review.csv`) holds anything below a confidence threshold or
  that failed discovery, for manual inspection — never silently dropped.

New stages (faculty, research, requirements) must follow this exact pattern for consistency.

## 7. Non-Goals (architectural)

- No database engine (Postgres/SQLite) in v1 — flat files are sufficient at this scale and keep the
  project zero-infrastructure to run.
- No async/concurrent scraping in v1 — keep it simple and polite to target servers; revisit only if
  runtime becomes a real bottleneck.
- No LLM in the core discovery pipeline (see Section 1). If added later for research summarization, it
  must be a clearly separated, optional module with its own file, not mixed into the deterministic
  scraping agents.