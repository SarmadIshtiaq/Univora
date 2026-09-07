# Univora

> Evidence-backed graduate program research automation.

Univora helps a graduate applicant turn a large, messy set of university websites into a structured research dataset that can be checked, filtered, and used for human decisions.

The current build focuses on:

```text
University
    ↓
Academic Program
    ↓
Faculty
```

The product is being built from the ground up with a strong emphasis on evidence, validation, resumability, and human review.

## What Univora is

Univora is a research-data pipeline.

It collects facts from official university sources and preserves the evidence behind those facts. The applicant remains the decision-maker.

The product principle is:

> **Human chooses. Univora researches.**

## Current v1 scope

The first version focuses only on three entities:

### 1. University

Identify the official university website/domain from a starting university list.

### 2. Program

Discover real academic graduate programs belonging to that university and preserve the official program source.

### 3. Faculty

Discover faculty associated with the relevant program or department and preserve their official profile sources.

The current pipeline is:

```text
Seed Universities
      ↓
Official University
      ↓
Academic Programs
      ↓
Faculty
```

## What is not part of the current build

The current build does not include:

* professor research extraction;
* admission requirement extraction;
* application/SOP/CV generation;
* professor outreach;
* application tracking;
* university ranking;
* professor ranking;
* recommendation or “best fit” scoring;
* automated decision-making;
* web dashboard;
* non-USA universities;
* mandatory LLM APIs;
* paid external APIs.

Future features must be deliberately added to the product documentation before implementation.

## Core product promise

**Never make the dataset look more complete than the evidence justifies.**

A missing fact is acceptable.

A guessed fact is not.

Every verified record must have a traceable official source URL. Anything uncertain must be marked for review or unresolved rather than silently invented.

## User workflow

The current v1 workflow is:

```text
1. Start with a university seed list
2. Resolve official university websites
3. Discover graduate programs
4. Discover faculty associated with those programs
5. Review the generated data
```

The outputs are intended to be simple and inspectable:

* CSV files for humans;
* JSON registries for machine state;
* source URLs for verification;
* review files for uncertain records.

## Build sequence

Do not start by writing large scrapers.

Build in this order:

```text
1. Product contract
2. Architecture + data contracts
3. Repository skeleton
4. Shared models / validation
5. Shared HTTP + registry infrastructure
6. Stage 1 — Universities
7. Stage 2 — Programs
8. Stage 3 — Faculty
9. Cross-stage validation
10. Small pilot
11. Full batch
```

Each stage must work independently before the next stage is allowed to depend on it.

## Documentation map

| File                         | Purpose                          |
| ---------------------------- | -------------------------------- |
| `README.md`                  | Project overview                 |
| `PRD.md`                     | Product requirements             |
| `Architecture.md`            | Detailed technical architecture  |
| `architecture-essentials.md` | Fast reference for coding agents |
| `CLAUDE.md`                  | Claude-specific coding rules     |
| `AGENTS.md`                  | General coding-agent rules       |

## Repository target

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
│   ├── university/
│   ├── program/
│   └── faculty/
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── review/
│
├── tests/
└── workflows/
    └── n8n/
```

## Definition of success

The current v1 is successful when a real USA university batch can move through:

```text
University → Program → Faculty
```

without hand-editing generated datasets, without fabricated facts, and without losing state between runs.

The system does not need to know everything.

It needs to know what it knows, where it learned it, and what still needs human review.
