# Univora — Product Requirements Document

## 1. Product definition

Univora is an evidence-backed research automation system for graduate-school discovery.

Given a starting list of USA universities, it discovers and structures:

```text
University → Program → Faculty
```

Every important extracted fact is linked to official-source evidence.

The system is designed for a graduate applicant who would otherwise spend hours manually opening university, department, program, and faculty pages.

## 2. Problem

Graduate-school research is fragmented.

For one target university, a user may need to inspect:

* the university website;
* graduate school pages;
* department pages;
* program pages;
* faculty directories;
* individual faculty profiles.

Doing this for many universities creates repetitive work and makes it easy to miss programs, confuse departments, rely on the wrong page, or lose the original evidence.

## 3. Target user

### Primary v1 user

A graduate applicant who wants a structured, evidence-backed research base before making application decisions.

## 4. Product principles

### P1 — Evidence first

Facts are useful only when their origin can be checked.

### P2 — Human remains the decision-maker

Univora researches and structures information. It does not decide where the user should apply.

### P3 — Prefer missing over fabricated

The system must be comfortable saying `unresolved` or `not found`.

### P4 — Independent stages

Every pipeline stage can be run, resumed, and validated independently.

### P5 — Human-reviewable outputs

CSV is part of the product, not merely a debugging format.

### P6 — Deterministic core

The v1 core pipeline does not require an LLM or paid external API.

## 5. Core workflow

```text
Seed universities
      ↓
Resolve official domains
      ↓
Discover academic programs
      ↓
Discover faculty
      ↓
Produce evidence-backed datasets
```

## 6. Functional requirements

| ID    | Requirement                                | Acceptance condition                                         |
| ----- | ------------------------------------------ | ------------------------------------------------------------ |
| FR-01 | Accept a university seed list              | Input contains stable university IDs and names               |
| FR-02 | Resolve official university domains        | Verified records contain official domain and source evidence |
| FR-03 | Discover programs                          | Every verified program has an official source URL            |
| FR-04 | Preserve university → program relationship | Program contains valid `university_id`                       |
| FR-05 | Discover faculty                           | Faculty record links to a valid university/program context   |
| FR-06 | Preserve faculty profile evidence          | Verified faculty has an official profile source URL          |
| FR-07 | Support uncertain outcomes                 | Uncertain records enter `review` or `unresolved`             |
| FR-08 | Support resumable execution                | Reruns do not create duplicate verified records              |
| FR-09 | Produce machine state                      | Every stage has a JSON registry                              |
| FR-10 | Produce human-reviewable data              | Every stage has a generated CSV                              |
| FR-11 | Enforce evidence                           | A verified record cannot exist without a valid source URL    |
| FR-12 | Preserve stage boundaries                  | Each stage consumes verified output from the previous stage  |
| FR-13 | Be polite to websites                      | Requests use timeout, delay, and bounded retry behavior      |

## 7. Evidence rules

### Source hierarchy

For v1, prefer:

1. official university domain;
2. official school/college/department domain;
3. official graduate program page;
4. official faculty directory/profile;
5. official university PDF belonging to the university.

Third-party rankings, aggregators, blogs, forums, and unofficial directories are not acceptable evidence for core entity facts.

### Evidence requirement

Each verified entity must carry:

* `source_url`
* `confidence`
* `status`
* `agent_version`

## 8. Status model

Use only these core statuses:

* `verified` — evidence was found and the result passed validation.
* `review` — a plausible result exists but confidence or attribution is insufficient.
* `unresolved` — the system could not find enough evidence for a valid result.

The system must not hide uncertainty behind a generic “completed” status.

## 9. Success criteria

v1 succeeds when:

1. official university-domain resolution works on a representative USA pilot;
2. program discovery correctly attributes programs to universities;
3. faculty discovery correctly attributes people to the appropriate program/department context;
4. every verified row has valid evidence;
5. reruns are idempotent;
6. uncertain discoveries remain visible in review outputs;
7. a fresh developer can understand and operate the project from the documentation and repository structure.

The exact coverage percentage should be measured during the pilot instead of inventing an arbitrary target before real-world testing.

## 10. v1 pilot

Use a small pilot of approximately 5–10 universities with different website structures.

The pilot should contain a mix of:

* large research universities;
* universities with department-specific sites;
* universities with straightforward program directories;
* universities with difficult or unusual site structures.

The pilot is for finding architecture and extraction problems before scaling.

## 11. Non-goals

The current version is not:

* a university ranking system;
* a professor ranking system;
* an admissions predictor;
* an application-management system;
* an outreach bot;
* a recommendation engine;
* an autonomous application agent;
* a dashboard application.

## 12. Release gates

A stage cannot be considered production-ready until:

* its schema is documented;
* its source policy is documented;
* its validator passes;
* its registry is resumable;
* its CSV output is reproducible;
* its review output is explicit;
* a real pilot run has been manually inspected.
