# CLAUDE.md — Univora Coding Instructions

## Start here

Before changing code, read:

1. `architecture-essentials.md`
2. `PRD.md`
3. `Architecture.md` when a decision affects schemas, stage boundaries, validation, or storage.

Do not begin implementation from a vague task description when the task changes product scope.

Product decisions belong in `PRD.md`.

## Current scope

The current product pipeline is:

```text
University → Program → Faculty
```

Do not add additional data domains without updating the product documentation first.

## Non-negotiable rules

### 1. Evidence is mandatory

A verified record must have a real official source URL.

Never create a value merely to fill a column.

### 2. No silent invention

When evidence is incomplete:

* use `review` or `unresolved`;
* record the reason;
* keep the candidate visible to the human.

### 3. Generated datasets are read-only outputs

Never manually patch:

```text
data/processed/*.csv
```

Change the producing logic and regenerate the dataset.

### 4. Preserve resumability

Every stage must have:

* stable IDs;
* registry state;
* deterministic output;
* rerun-safe behavior.

### 5. Keep stage ownership clean

University logic belongs to Stage 1.

Program logic belongs to Stage 2.

Faculty logic belongs to Stage 3.

Shared concerns belong in `agents/common/`.

### 6. No core LLM calls

Do not call an LLM from the deterministic discovery pipeline.

Optional future AI capabilities must be isolated from the core discovery system.

### 7. Respect external sites

Use the shared HTTP helper.

Do not add unbounded parallel requests.

Keep request delay, timeout, retry, and user-agent behavior centralized.

## Before implementing a new stage

Document:

1. input dataset;
2. entity schema;
3. ID strategy;
4. source policy;
5. status policy;
6. confidence rules;
7. registry behavior;
8. review behavior.

Then write code.

## Testing expectations

For changes that affect data correctness, add tests for:

* schema validation;
* source/domain validation;
* deterministic IDs;
* duplicate prevention;
* registry behavior;
* parser behavior.

Use fixtures rather than live websites for most parser tests.

## Definition of done

A task is not finished merely because the script runs.

It is finished when:

* real input can be processed;
* output is evidence-backed;
* reruns are safe;
* uncertain records are visible;
* tests cover changed behavior;
* documentation still matches implementation.
