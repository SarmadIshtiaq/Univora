# Univora — Architecture Essentials

Read this before coding.

## Product

Univora is an evidence-backed graduate research pipeline.

```text
University → Program → Faculty → Research → Requirements
```

The user decides. The system researches.

## Hard rules

1. **Evidence or nothing.** Verified records require a real source URL.
2. **No guessing.** Uncertain facts become `review` or `unresolved`.
3. **Stable IDs.** Never use changing row numbers as entity identity.
4. **Stage independence.** Stage N consumes verified Stage N-1 output.
5. **CSV + JSON.** Every stage produces a generated CSV and a resumability registry.
6. **Generated data is not hand-edited.**
7. **Official sources only** for core entity facts.
8. **No mandatory LLM/paid API** in the v1 discovery core.
9. **Polite HTTP.** Shared timeout/delay/retry policy.
10. **No silent scope expansion.**

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

Research
- research_id
- faculty_id
- research_areas
- summary
- source_url
- confidence
- status
- agent_version

Requirement
- requirement_id
- program_id
- requirement_type
- value
- applies_to
- source_url
- confidence
- status
- agent_version
```

## Stage boundaries

```text
raw seed
  ↓
university.csv + university_registry.json
  ↓
programs.csv + program_registry.json
  ↓
faculty.csv + faculty_registry.json
  ↓
research.csv + research_registry.json
  ↓
requirements.csv + requirements_registry.json
```

Every stage also has a review CSV.

## Repository principle

Keep the core small:

```text
agents/common
agents/university
agents/program
agents/faculty
agents/research
agents/requirements
data/raw
data/processed
data/review
tests
```

## Before adding code

Ask:

- Which stage owns this logic?
- What is the input contract?
- What is the output schema?
- What evidence proves the result?
- How will a rerun behave?
- What happens when evidence is weak?

If those are not answered, the code is not ready to be written.
