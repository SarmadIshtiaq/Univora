# Univora — Architecture

## 1. Architecture goal

Build a small, deterministic, evidence-preserving research pipeline that can scale through many university websites without turning into an untraceable scraping system.

The architecture optimizes for:

- correctness;
- traceability;
- resumability;
- simple local execution;
- inspectable files;
- clear stage ownership.

It does not optimize for maximum concurrency, maximum automation, or maximum feature count.

## 2. System shape

```text
                    ┌─────────────────────┐
                    │ Seed university list│
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Stage 1: University │
                    │ domain resolution   │
                    └──────────┬──────────┘
                               │ verified CSV
                               ▼
                    ┌─────────────────────┐
                    │ Stage 2: Programs   │
                    └──────────┬──────────┘
                               │ verified CSV
                               ▼
                    ┌─────────────────────┐
                    │ Stage 3: Faculty    │
                    └──────────┬──────────┘
                               │ verified CSV
                               ▼
                    ┌─────────────────────┐
                    │ Stage 4: Research   │
                    └──────────┬──────────┘
                               │ verified CSV
                               ▼
                    ┌─────────────────────┐
                    │ Stage 5: Requirements│
                    └──────────┬──────────┘
                               │
                               ▼
                    Evidence-backed dataset
```

Evidence is a cross-cutting concern across all stages, not a separate scraper stage.

## 3. Technology boundary

### v1

- Python 3.10+
- `requests`
- `beautifulsoup4`
- `pandas`
- `pydantic`
- standard library

### Deliberately not required

- Postgres / SQLite
- Redis
- message queues
- browser automation
- async scraping frameworks
- paid scraping APIs
- mandatory LLM APIs
- web frontend

A future UI may be added on top of stable outputs without changing the discovery core.

## 4. Repository layout

```text
Univora/
├── README.md
├── PRD.md
├── Architecture.md
├── architecture-essentials.md
├── CLAUDE.md
├── AGENTS.md
├── requirements.txt
│
├── agents/
│   ├── common/
│   │   ├── models.py
│   │   ├── evidence.py
│   │   ├── registry.py
│   │   ├── http.py
│   │   ├── ids.py
│   │   └── validation.py
│   │
│   ├── university/
│   │   ├── seed.py
│   │   └── resolve.py
│   │
│   ├── program/
│   │   └── discover.py
│   │
│   ├── faculty/
│   │   └── discover.py
│   │
│   ├── research/
│   │   └── extract.py
│   │
│   └── requirements/
│       └── extract.py
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── review/
│
├── tests/
│   ├── common/
│   ├── university/
│   ├── program/
│   ├── faculty/
│   ├── research/
│   └── requirements/
│
├── workflows/
│   └── n8n/
│
└── docs/
```

### Important distinction

`data/raw/` contains user/source inputs and should not be rewritten by pipeline code.

`data/processed/` contains generated canonical datasets.

`data/review/` contains generated uncertainty/failure outputs that need human attention.

## 5. Domain model

Every entity inherits from `EvidenceBase`.

```python
class EvidenceBase(BaseModel):
    source_url: str | None
    confidence: float
    status: Literal["verified", "review", "unresolved"]
    agent_version: str
```

For strict publication, `source_url` must be non-null when `status == "verified"`.

The common model can also expose `evidence` for multiple sources:

```python
class EvidenceItem(BaseModel):
    source_url: str
    source_type: str
    captured_at: str
    locator: str | None = None
```

Whether multiple evidence items are emitted in v1 can remain optional, but the architecture must not make multi-source evidence impossible.

### University

```python
class University(EvidenceBase):
    university_id: str
    university_name: str
    country: str
    official_domain: str | None
    official_website: str | None
    discovery_method: str
```

### Program

```python
class Program(EvidenceBase):
    program_id: str
    university_id: str
    school_name: str | None
    department_name: str | None
    program_name: str
    degree_level: str
    program_url: str | None
```

### Faculty

```python
class Faculty(EvidenceBase):
    faculty_id: str
    program_id: str
    university_id: str
    full_name: str
    title: str | None
    profile_url: str
    email: str | None
```

### Professor Research

```python
class ProfessorResearch(EvidenceBase):
    research_id: str
    faculty_id: str
    research_areas: list[str]
    summary: str | None
```

The `summary` must be extracted or quoted from evidence according to the stage policy. A generated LLM summary is not allowed in the deterministic core.

### Requirement

```python
class Requirement(EvidenceBase):
    requirement_id: str
    program_id: str
    requirement_type: str
    value: str
    applies_to: str | None
```

## 6. Canonical identifiers

IDs must be deterministic and stable.

Recommended v1 format:

```text
UNI-{normalized-university-key}
PROG-{university_id}-{normalized-program-key}
FAC-{program_id}-{normalized-faculty-key}
RES-{faculty_id}-{normalized-research-key}
REQ-{program_id}-{normalized-requirement-key}
```

Rules:

- lowercase/uppercase normalization is standardized in one helper;
- punctuation is normalized;
- IDs do not contain source URL query strings;
- an ID must remain stable when a page is re-scraped;
- the ID generator must have unit tests.

Do not use row numbers that change when sorting.

## 7. Stage contracts

### Stage 1 — University

Input:

```text
data/raw/universities.csv
```

Output:

```text
data/processed/universities.csv
data/processed/university_registry.json
data/review/universities_review.csv
```

Responsibility:

- normalize seed names;
- resolve the official university website/domain;
- validate that the site represents the university;
- save evidence and confidence.

Stage 1 does not discover programs.

### Stage 2 — Program

Input:

```text
data/processed/universities.csv
```

Only `verified` universities enter automatic processing.

Output:

```text
data/processed/programs.csv
data/processed/program_registry.json
data/review/programs_review.csv
```

Responsibility:

- discover genuine academic programs;
- capture school/department context;
- capture degree level;
- preserve official program URL;
- avoid confusing news articles, alumni stories, certificates, and unrelated pages with academic programs.

### Stage 3 — Faculty

Input:

```text
data/processed/programs.csv
```

Only `verified` programs enter automatic processing.

Output:

```text
data/processed/faculty.csv
data/processed/faculty_registry.json
data/review/faculty_review.csv
```

Responsibility:

- identify appropriate faculty directories;
- discover people associated with the program/department;
- capture faculty profile pages;
- avoid treating administrators, staff, students, alumni, or emeritus-only pages as active faculty unless policy explicitly permits them.

### Stage 4 — Research

Input:

```text
data/processed/faculty.csv
```

Only `verified` faculty enter automatic processing.

Output:

```text
data/processed/research.csv
data/processed/research_registry.json
data/review/research_review.csv
```

Responsibility:

- extract research areas from faculty evidence;
- preserve the faculty relationship;
- distinguish explicit research statements from incidental keywords;
- avoid inventing research areas based only on publication titles.

### Stage 5 — Requirements

Input:

```text
data/processed/programs.csv
```

Only `verified` programs enter automatic processing.

Output:

```text
data/processed/requirements.csv
data/processed/requirements_registry.json
data/review/requirements_review.csv
```

Responsibility:

- find official admissions/requirements information;
- capture requirement type and value;
- preserve dates in a consistent representation where possible;
- distinguish program-specific rules from university-wide rules;
- preserve exceptions instead of flattening them into misleading statements.

## 8. Registry contract

Every stage has a registry keyed by stable entity ID.

Example:

```json
{
  "PROG-UNI-STANFORD-UNIVERSITY-COMPUTER-SCIENCE-MS": {
    "entity_id": "PROG-UNI-STANFORD-UNIVERSITY-COMPUTER-SCIENCE-MS",
    "input_fingerprint": "sha256:...",
    "status": "verified",
    "last_run_at": "2026-09-07T10:00:00Z",
    "agent_version": "program-0.1.0",
    "source_url": "https://...",
    "error": null
  }
}
```

The registry is machine state.

The CSV is the human-reviewable current output.

Do not treat the CSV as a writable database.

## 9. Idempotency

A stage re-run with the same effective input should:

- preserve stable IDs;
- update records only when evidence or extraction state changed;
- never append duplicates just because the stage ran again;
- preserve unresolved/review state until new evidence changes the outcome;
- never erase a previously verified record merely because one temporary request failed.

Use deterministic IDs and input fingerprints to support this.

## 10. HTTP policy

All web requests go through a shared HTTP helper.

The helper owns:

- timeout;
- retry policy;
- backoff;
- user agent;
- request delay;
- response-size limits where appropriate;
- basic status handling.

Agents should not each implement their own ad-hoc `requests.get()` behavior.

Do not add parallel scraping until there is a measured performance problem and a deliberate rate-limit design.

## 11. URL and domain policy

A source is allowed when it belongs to the verified university domain or an official university-controlled subdomain.

The pipeline should normalize URLs before comparison:

- lowercase hostname;
- strip default ports;
- normalize trailing slash;
- preserve meaningful paths;
- reject unrelated external hosts.

A university may have multiple official domains/subdomains. Stage 1 should store a canonical domain plus, where necessary, an approved-domain list.

## 12. Discovery quality model

Confidence is a numeric signal, but it must not become a fake probability.

Use it as a rules-based confidence score derived from explicit signals, for example:

```text
+ official-domain match
+ direct program/faculty page
+ expected contextual terms
+ exact university name match
- generic/news content
- third-party host
- ambiguous page role
- contradictory context
```

The score should be documented and tested.

A low score goes to `review` rather than being “rounded up” to verified.

## 13. Validation

Before writing a verified row:

1. Pydantic schema validation passes.
2. required ID fields are present.
3. relationship IDs exist in the previous-stage dataset.
4. source URL is present and valid.
5. source URL belongs to an approved official domain.
6. status is allowed.
7. confidence is within `[0, 1]`.
8. no required field is silently fabricated.

A final cross-stage validator should be able to detect orphaned records.

## 14. Error handling

Classify failures:

- `not_found` — no suitable page discovered;
- `blocked` — target site blocked the request;
- `timeout` — request timed out;
- `parse_error` — page was retrieved but could not be interpreted;
- `ambiguous` — multiple plausible candidates;
- `validation_error` — candidate failed publication rules.

Errors are state, not exceptions to hide.

## 15. Testing strategy

### Unit tests

Test:

- ID generation;
- URL normalization;
- domain matching;
- confidence rules;
- parsing functions;
- registry read/write;
- idempotency;
- schema validation.

### Fixture tests

Store small HTML fixtures representing:

- normal university page;
- JS-heavy page;
- program directory;
- faculty directory;
- faculty profile;
- admissions page;
- ambiguous page.

Do not make the test suite depend entirely on live websites.

### Integration tests

Run a small set against live official domains manually or on a controlled cadence.

Do not make ordinary unit-test runs hammer universities.

## 16. Build phases

### Phase 0 — Foundation

- create repository structure;
- implement shared models;
- implement evidence/domain/ID validation;
- implement registry utilities;
- implement HTTP helper;
- add tests.

### Phase 1 — University

- seed import;
- domain resolver;
- validation;
- registry;
- review output.

### Phase 2 — Program

- program discovery;
- deduplication;
- contextual attribution;
- tests.

### Phase 3 — Faculty

- faculty directory discovery;
- profile extraction;
- tests.

### Phase 4 — Research

- research extraction;
- tests for explicit research statements and ambiguous pages.

### Phase 5 — Requirements

- requirement discovery;
- deadline/value normalization;
- program-vs-university scope handling.

### Phase 6 — Pilot

Run 5–10 varied universities end to end.

Only after the pilot is reviewed should the full USA batch be run.

## 17. Definition of architectural success

A developer should be able to answer these five questions without opening implementation code:

1. What is the pipeline?
2. What is the schema for each entity?
3. What counts as evidence?
4. How does a stage resume?
5. What happens when the system is uncertain?

Those answers belong in the documentation, not hidden in scripts.
