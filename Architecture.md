# Univora — Architecture

## 1. Architecture goal

Build a small, deterministic, evidence-preserving research pipeline that can process many university websites without becoming an untraceable scraping system.

The architecture optimizes for:

* correctness;
* traceability;
* resumability;
* simple local execution;
* inspectable files;
* clear stage ownership.

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
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Stage 2: Programs   │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Stage 3: Faculty    │
                    └──────────┬──────────┘
                               │
                               ▼
                    Evidence-backed dataset
```

Evidence is a cross-cutting concern across all three stages.

## 3. Technology boundary

### v1

* Python 3.10+
* `requests`
* `beautifulsoup4`
* `pandas`
* `pydantic`
* Python standard library

### Not required for v1

* Postgres;
* Redis;
* message queues;
* async scraping frameworks;
* paid scraping APIs;
* mandatory LLM APIs;
* web frontend.

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
│   └── faculty/
│       └── discover.py
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
│   └── faculty/
│
├── workflows/
│   └── n8n/
│
└── docs/
```

## 5. Data directories

### `data/raw/`

Human/source inputs.

Examples:

```text
data/raw/universities.csv
```

Pipeline code should not mutate raw input files.

### `data/processed/`

Canonical generated datasets.

Examples:

```text
data/processed/universities.csv
data/processed/programs.csv
data/processed/faculty.csv
```

### `data/review/`

Generated records that need human attention.

Examples:

```text
data/review/universities_review.csv
data/review/programs_review.csv
data/review/faculty_review.csv
```

## 6. Domain model

All core entities inherit from an evidence base.

```python
class EvidenceBase(BaseModel):
    source_url: str | None
    confidence: float
    status: Literal["verified", "review", "unresolved"]
    agent_version: str
```

For a verified record:

```text
source_url != null
0 <= confidence <= 1
status == "verified"
```

## 7. University model

```python
class University(EvidenceBase):
    university_id: str
    university_name: str
    country: str
    official_domain: str | None
    official_website: str | None
    discovery_method: str
```

## 8. Program model

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

## 9. Faculty model

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

## 10. Canonical identifiers

IDs must be deterministic and stable.

Recommended format:

```text
UNI-{normalized-university-key}
PROG-{university_id}-{normalized-program-key}
FAC-{program_id}-{normalized-faculty-key}
```

Rules:

* normalization is implemented in one shared helper;
* punctuation is normalized consistently;
* IDs do not contain URL query strings;
* IDs must survive reruns;
* IDs must not depend on CSV row order;
* ID generation must have unit tests.

## 11. Stage 1 — University

### Input

```text
data/raw/universities.csv
```

### Outputs

```text
data/processed/universities.csv
data/processed/university_registry.json
data/review/universities_review.csv
```

### Responsibility

Stage 1:

* normalizes seed university names;
* resolves the official university website/domain;
* checks whether the candidate site represents the university;
* records evidence;
* assigns status and confidence.

Stage 1 does not discover programs.

## 12. Stage 2 — Program

### Input

```text
data/processed/universities.csv
```

Only verified universities enter automatic processing.

### Outputs

```text
data/processed/programs.csv
data/processed/program_registry.json
data/review/programs_review.csv
```

### Responsibility

Stage 2:

* discovers academic programs;
* captures school and department context;
* captures degree level;
* stores the official program URL;
* prevents unrelated pages from being classified as programs.

Examples of pages that should not automatically become programs:

* news articles;
* alumni stories;
* event pages;
* individual course pages;
* certificates;
* rankings;
* generic search pages.

## 13. Stage 3 — Faculty

### Input

```text
data/processed/programs.csv
```

Only verified programs enter automatic processing.

### Outputs

```text
data/processed/faculty.csv
data/processed/faculty_registry.json
data/review/faculty_review.csv
```

### Responsibility

Stage 3:

* discovers relevant faculty directories;
* identifies faculty associated with the program/department;
* captures official faculty profile URLs;
* preserves university/program relationships;
* avoids classifying unrelated people as faculty.

The stage must carefully distinguish:

* faculty;
* staff;
* administrators;
* students;
* alumni;
* visitors;
* unrelated researchers.

The exact faculty inclusion policy should be implemented explicitly rather than guessed.

## 14. Registry contract

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

Do not treat the CSV as a database.

## 15. Idempotency

A stage rerun with the same effective input should:

* preserve stable IDs;
* avoid duplicate records;
* update records only when evidence or extraction state changes;
* preserve a previously verified record through a temporary request failure;
* never silently erase verified information.

Deterministic IDs and input fingerprints should be used to support this.

## 16. HTTP policy

All web requests go through a shared HTTP helper.

The helper owns:

* timeout;
* retry policy;
* backoff;
* user agent;
* request delay;
* status handling;
* bounded request behavior.

Individual stage agents should not implement separate request policies.

Do not introduce parallel scraping until performance requirements justify it and rate limiting has been designed.

## 17. URL and domain policy

A source is allowed when it belongs to the verified university domain or an approved university-controlled subdomain.

URL normalization should handle:

* hostname normalization;
* default ports;
* trailing slashes;
* meaningful paths;
* obvious tracking parameters where appropriate.

A university may have multiple official domains/subdomains.

The system should support a canonical domain plus approved domains where needed.

## 18. Confidence model

Confidence is a rules-based quality signal.

It is not a fake probability.

Possible positive signals:

```text
+ official-domain match
+ direct program page
+ direct faculty profile
+ expected university context
+ expected department context
```

Possible negative signals:

```text
- generic/news page
- third-party host
- ambiguous page role
- contradictory context
```

Confidence rules must be explicit and testable.

A weak result goes to `review` rather than being automatically promoted to `verified`.

## 19. Validation

Before writing a verified row:

1. Pydantic schema validation passes.
2. Required ID fields are present.
3. Relationship IDs exist in the previous-stage dataset.
4. Source URL is present.
5. Source URL belongs to an approved official domain.
6. Status is valid.
7. Confidence is within `[0, 1]`.
8. No field has been silently fabricated.

A cross-stage validator should detect orphaned records.

## 20. Error handling

Use controlled error categories:

* `not_found`
* `blocked`
* `timeout`
* `parse_error`
* `ambiguous`
* `validation_error`

Errors should become visible stage state.

They must not disappear inside generic exception handling.

## 21. Testing strategy

### Unit tests

Test:

* ID generation;
* URL normalization;
* domain matching;
* confidence rules;
* parsers;
* registry read/write;
* idempotency;
* schema validation.

### Fixture tests

Maintain small HTML fixtures for:

* normal university pages;
* program directories;
* faculty directories;
* faculty profiles;
* ambiguous pages;
* JS-heavy pages where relevant.

Most parser tests should use fixtures rather than live websites.

### Integration tests

Use a small controlled set of real official university websites.

Normal unit tests should not repeatedly hammer live sites.

## 22. Build phases

### Phase 0 — Foundation

* repository structure;
* shared domain models;
* evidence validation;
* stable IDs;
* registry utilities;
* HTTP helper;
* test foundation.

### Phase 1 — University

* seed import;
* domain resolution;
* validation;
* registry;
* review output.

### Phase 2 — Program

* program discovery;
* deduplication;
* contextual attribution;
* validation;
* tests.

### Phase 3 — Faculty

* faculty directory discovery;
* faculty/profile extraction;
* validation;
* tests.

### Phase 4 — Pilot

Run 5–10 varied universities end to end.

Inspect the output manually.

Only after the pilot should the system scale to a larger batch.

## 23. Architectural success

A developer should be able to answer these questions without opening implementation code:

1. What is the pipeline?
2. What is the schema for each entity?
3. What counts as evidence?
4. How does a stage resume?
5. What happens when the system is uncertain?

Those answers belong in the documentation.
