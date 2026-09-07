# Univora

> Evidence-backed graduate program research automation.

Univora helps a graduate applicant turn a large, messy set of university websites into a structured research dataset that can be checked, filtered, and used for human decisions.

The core idea is:

```text
University
    ↓
Academic Program
    ↓
Faculty
    ↓
Professor Research
    ↓
Admission Requirements
    ↓
Evidence
```

## What Univora is

Univora is a research-data pipeline, not a recommendation engine.

It collects facts from official university sources and preserves the evidence behind those facts. The applicant remains the decision-maker.

The product principle is:

> **Human chooses. Univora researches. Automation handles repetitive work.**

## The v1 user experience

v1 intentionally has no web dashboard.

The user works with:

1. a starting university list;
2. command-line pipeline stages;
3. generated CSV files for human review;
4. JSON registries for machine state and resumability;
5. source URLs for verification.

A successful run should let the user answer questions such as:

- What graduate programs exist at this university?
- Which department owns the program?
- Which faculty are associated with it?
- What does each faculty member say they research?
- What are the admission requirements and deadlines?
- Where did each fact come from?

## Product boundary

### In scope for v1

- USA university discovery / official-domain resolution
- academic program discovery
- faculty discovery
- faculty profile collection
- professor research-area extraction
- admission requirement extraction
- source/evidence tracking
- resumable batch processing
- review queues for uncertain records
- CSV + JSON outputs
- CLI operation

### Explicitly out of scope for v1

- application/SOP/CV generation
- automated professor outreach
- email sending
- application tracking
- school or professor ranking
- “best fit” recommendations
- automated research-interest matching
- a web dashboard
- non-USA universities
- paid APIs or mandatory LLM APIs

Those can become later products, but they are not part of the first reliable research engine.

## Core product promise

**Never make the dataset look more complete than the evidence justifies.**

A missing fact is acceptable.

A guessed fact is not.

Every stored fact must have a traceable source URL. Anything uncertain must be marked for review or unresolved rather than silently invented.

## Build sequence

Do not start by writing scrapers.

The build order is:

```text
1. Product contract
2. Architecture + data contracts
3. Repository skeleton
4. Shared models / validation
5. Stage 1 — universities
6. Stage 2 — programs
7. Stage 3 — faculty
8. Stage 4 — professor research
9. Stage 5 — requirements
10. Cross-stage validation
11. Pilot run on a small university set
12. Scale to the full USA batch
```

Each stage must work independently before the next stage is allowed to depend on it.

## Documentation map

| File | Purpose |
|---|---|
| `README.md` | Human-facing project overview |
| `PRD.md` | What the product must do and why |
| `Architecture.md` | How the product is structured |
| `architecture-essentials.md` | Fast reference for coding agents |
| `CLAUDE.md` | Claude-specific operating rules |
| `AGENTS.md` | General coding-agent operating rules |

## What “done” means

v1 is done when a real USA university batch can move through the pipeline without hand-editing generated datasets, without fabricated facts, and without losing state between runs.

The final dataset does not need to know everything.

It needs to know what it knows, where it learned it, and what still needs human review.
