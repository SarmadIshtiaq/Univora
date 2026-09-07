# Univora — Architecture Essentials

Read this before coding.

## Product

Univora is an evidence-backed graduate research pipeline.

```text
University → Program → Faculty
```

The user decides. The system researches.

## Hard rules

1. **Evidence or nothing.** Verified records require a real source URL.
2. **No guessing.** Uncertain facts become `review` or `unresolved`.
3. **Stable IDs.** Never use changing row numbers as entity identity.
4. **Stage independence.** Each stage consumes verified output from the previous stage.
5. **CSV + JSON.** Every stage produces generated CSV output and a resumability registry.
6. **Generated data is not hand-edited.**
7. **Official sources only** for core entity facts.
8. **No mandatory LLM/paid API** in the v1 discovery core.
9. **Polite HTTP.** Shared timeout/delay/retry policy.
10. **No silent scope expansion.**

## Current pipeline

```text
raw university seed
        ↓
university.csv
        ↓
programs.csv
        ↓
faculty.csv
```

Each stage also produces:

```text
registry.json
review.csv
```

## Canonical models

```text
University
- university_id
- university_name
- country
- official_domain
- official_website
- discovery_method
- source_url
- confidence
- status
- agent_version

Program
- program_id
- university_id
- school_name
- department_name
- program_name
- degree_level
- program_url
- source_url
- confidence
- status
- agent_version

Faculty
- faculty_id
- program_id
- university_id
- full_name
- title
- profile_url
- email
- source_url
- confidence
- status
- agent_version
```

## Stage boundaries

```text
Stage 1
University

Stage 2
Program

Stage 3
Faculty
```

Do not make a later stage redo the work of an earlier stage.

## Repository principle

Keep the core small:

```text
agents/common
agents/university
agents/program
agents/faculty
data/raw
data/processed
data/review
tests
workflows/n8n
```

## Before adding code

Ask:

* Which stage owns this logic?
* What is the input contract?
* What is the output schema?
* What evidence proves the result?
* How will a rerun behave?
* What happens when evidence is weak?

If those questions are not answered, the code is not ready to be written.
