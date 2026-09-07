# AGENTS.md — Instructions for Coding Agents

This file applies to any coding agent working in the repository.

## Mission

Build Univora as a reliable evidence-backed research pipeline, not as a collection of unrelated scrapers.

The product pipeline is:

```text
University → Program → Faculty → Research → Requirements
```

## Required behavior

### Evidence

For every entity:

- store the source URL;
- preserve confidence;
- store a controlled status;
- never fabricate a missing field.

### Resumability

Every stage:

- uses stable entity IDs;
- writes a JSON registry;
- writes a generated CSV;
- avoids duplicate verified rows;
- preserves previous verified state through temporary failures.

### Review

Ambiguous or low-confidence discoveries go to:

```text
data/review/<stage>_review.csv
```

They must not disappear.

### Scope

v1 excludes:

- recommendations;
- rankings;
- application generation;
- outreach automation;
- non-USA universities;
- mandatory LLM usage;
- dashboard/frontend work.

Do not add these unless the product documentation is deliberately changed first.

## Repository conventions

```text
agents/common/          shared infrastructure
agents/university/      Stage 1
agents/program/         Stage 2
agents/faculty/         Stage 3
agents/research/        Stage 4
agents/requirements/    Stage 5
data/raw/               source inputs, do not mutate
data/processed/         canonical generated datasets
data/review/            human review queues
tests/                  tests by stage
workflows/n8n/          optional orchestration
```

## Coding constraints

Prefer:

- small functions;
- explicit inputs/outputs;
- Pydantic models;
- deterministic normalization;
- standard Python libraries;
- shared HTTP behavior;
- testable parsing functions.

Avoid:

- hidden global state;
- duplicate implementations of the same stage;
- large “god scripts”;
- per-agent request policies;
- parsing logic mixed with persistence logic;
- unverified data enrichment.

## Change discipline

Before changing a schema, check:

- PRD functional requirements;
- Architecture domain model;
- downstream foreign keys;
- CSV column contract;
- registry compatibility.

Before changing a stage, check how its output is consumed by the next stage.

## No manual patching

Generated CSV files are outputs.

If a row is wrong:

1. fix the producing logic;
2. rerun;
3. inspect the result;
4. use the review mechanism for unresolved cases.

## Security and privacy

Do not store credentials, cookies, session tokens, personal applicant data, or secrets in the repository.

`.env` files and local credentials must remain ignored.

## Completion checklist

Before declaring a change complete:

- [ ] scope still matches `PRD.md`;
- [ ] architecture still matches `Architecture.md`;
- [ ] schema validation passes;
- [ ] tests pass;
- [ ] IDs are stable;
- [ ] source URLs are valid for verified records;
- [ ] rerun does not duplicate data;
- [ ] review cases remain visible;
- [ ] no new dependency was added without justification.
