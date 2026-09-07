# Univora — Product Requirements Document

## 1. Product definition

Univora is an evidence-backed research automation system for graduate-school discovery.

Given a starting list of USA universities, it discovers and structures:

```text
University → Program → Faculty → Research → Requirements
```

Every important extracted fact is linked to official-source evidence.

The system is designed for a graduate applicant who would otherwise spend hours manually opening university, department, program, and faculty pages.

## 2. Problem

Graduate-school research is fragmented.

For one target university, a user may need to inspect:

- the university website;
- graduate school pages;
- department pages;
- program pages;
- faculty directories;
- individual faculty profiles;
- admissions requirement pages;
- deadline pages;
- PDF handbooks or program guides.

The same information is expressed differently across institutions.

Doing this for 50–200 universities creates repetitive work and makes it easy to miss programs, confuse departments, rely on stale pages, or lose the original evidence.

## 3. Target user

### Primary v1 user

A graduate applicant who wants a structured, evidence-backed research base before making application decisions.

### Secondary future users

Other applicants using the system locally or through a future shared application.

## 4. Product principles

### P1 — Evidence first

Facts are useful only when their origin can be checked.

### P2 — Human remains the decision-maker

Univora researches and structures information. It does not decide where the user should apply.

### P3 — Prefer missing over fabricated

The system must be comfortable saying “unresolved” or “not found.”

### P4 — Independent stages

Every pipeline stage can be run, resumed, and validated independently.

### P5 — Human-reviewable outputs

CSV is intentionally part of the product, not merely a debugging format.

### P6 — Deterministic core

The v1 core pipeline does not require an LLM or paid external API.

Optional AI capabilities can be considered later, but must not weaken evidence traceability.

## 5. Core workflow

```text
Seed universities
      ↓
Resolve official domains
      ↓
Discover real academic programs
      ↓
Discover faculty attached to relevant programs/departments
      ↓
Extract current research information from faculty sources
      ↓
Extract admission requirements for the program
      ↓
Produce evidence-backed datasets + review queues
```

## 6. Functional requirements

| ID | Requirement | Acceptance condition |
|---|---|---|
| FR-01 | Accept a university seed list | Input file contains stable university IDs and names |
| FR-02 | Resolve official university domains | Successful records contain a verified official domain and source evidence |
| FR-03 | Discover programs from official university domains | Every program record has a source URL on the allowed university domain |
| FR-04 | Preserve university → program relationships | Program contains a valid `university_id` |
| FR-05 | Discover faculty | Faculty record links to a program/department and has a profile source |
| FR-06 | Extract research | Research record links to faculty and preserves source evidence |
| FR-07 | Extract requirements | Requirement record links to a program and preserves source evidence |
| FR-08 | Support uncertain outcomes | Uncertain/failed records enter `review` or `unresolved`, never disappear silently |
| FR-09 | Resume processing | Rerunning a stage does not duplicate verified records |
| FR-10 | Produce machine state | Each stage has a JSON registry |
| FR-11 | Produce human-reviewable data | Each stage has a generated CSV |
| FR-12 | Enforce evidence | A publishable record cannot exist without a source URL |
| FR-13 | Keep stage boundaries | Stage N reads verified output from Stage N-1 rather than redoing earlier work |
| FR-14 | Be polite to sites | Requests use timeout, delay, and bounded retry behavior |
| FR-15 | Avoid hidden product expansion | No recommendation, outreach, or application automation in v1 |

## 7. Evidence rules

### Source hierarchy

For v1, prefer sources in this order:

1. official university domain;
2. official school/college/department domain that belongs to the university;
3. official program page;
4. official faculty profile;
5. official university PDF/handbook.

Third-party rankings, aggregator sites, blogs, and forums are not acceptable evidence for core entity facts.

### Evidence requirement

Each persisted entity must carry at least:

- `source_url`
- `confidence`
- `status`
- `agent_version`

For facts that need more than one supporting source, the data model should allow multiple evidence items rather than overwriting the primary source.

## 8. Status model

Use only these core statuses in v1:

- `verified` — evidence was found and the extracted value passed validation.
- `review` — a plausible result exists but confidence or attribution is insufficient for automatic acceptance.
- `unresolved` — the stage could not find enough evidence to produce a valid result.

The system must never invent a fourth “completed” state that hides the evidence quality.

## 9. Success criteria

v1 succeeds when:

1. official university-domain resolution works reliably for a representative USA batch;
2. program discovery returns correctly attributed programs for most universities that have discoverable official program pages;
3. faculty and research extraction works for a pilot subset;
4. requirements extraction works for a pilot subset;
5. every published row passes evidence validation;
6. reruns are idempotent;
7. uncertain discoveries are visible in review outputs;
8. a fresh developer can understand and operate the project from the six Markdown documents and the repository structure.

The exact percentage targets should be measured after the pilot. Do not optimize prematurely for an arbitrary coverage number that encourages fabricated data.

## 10. v1 pilot

Before large-scale execution, use a deliberately small pilot:

- 5–10 universities;
- different website structures;
- at least one large research university;
- at least one university with department-specific sites;
- at least one university where program and faculty information are easy to locate;
- at least one difficult case.

The pilot is for discovering architecture problems, not proving final coverage.

## 11. Future scope

Possible later versions:

- research-interest matching;
- personal profile / preference input;
- application tracking;
- outreach management;
- SOP/CV/email assistance;
- ranking or prioritization;
- web dashboard;
- additional countries;
- optional LLM-based summarization with explicit provenance.

None of these should leak into v1 implementation.

## 12. Product-level non-goals

Univora is not:

- a university ranking website;
- an admissions decision predictor;
- an autonomous application agent;
- a professor-contact bot;
- a chatbot that answers from unverified web content.

## 13. Release gates

A stage cannot be considered production-ready until:

- its schema is documented;
- its source policy is documented;
- its validator passes;
- its registry is resumable;
- its generated CSV is reproducible from registry state;
- its review output is explicit;
- a real pilot run has been inspected by a human.
