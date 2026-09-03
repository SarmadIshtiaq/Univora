from __future__ import annotations

import json
import re
from pathlib import Path
from difflib import SequenceMatcher
from typing import Any

import pandas as pd
import requests


# ==============================================================
# PATHS
# ==============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "universities_usa.csv"
)

CURRENT_OUTPUT = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "university_sources.csv"
)

REGISTRY_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "university_registry.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "university_sources_bulk.csv"
)

REVIEW_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "university_review_bulk.csv"
)

SOURCE_URL = (
    "https://raw.githubusercontent.com/Hipo/"
    "university-domains-list/master/"
    "world_universities_and_domains.json"
)


# ==============================================================
# HTTP
# ==============================================================

HEADERS = {
    "User-Agent": (
        "Univora/1.0 "
        "(university discovery research system)"
    )
}

TIMEOUT = 30


# ==============================================================
# HELPERS
# ==============================================================

def clean(value: Any) -> str:
    if value is None:
        return ""

    text = str(value).strip()

    if text.lower() == "nan":
        return ""

    return text


def normalize_name(name: str) -> str:

    text = clean(name).lower()

    text = (
        text
        .replace("’", "'")
        .replace("–", "-")
        .replace("—", "-")
        .replace("&", " and ")
    )

    # Remove parenthetical acronym.
    text = re.sub(
        r"\([^)]*\)",
        "",
        text,
    )

    text = re.sub(
        r"[/|,;:]+",
        " ",
        text,
    )

    text = re.sub(
        r"-+",
        " ",
        text,
    )

    # Remove leading THE.
    text = re.sub(
        r"^\s*the\s+",
        "",
        text,
    )

    # Normalize common campus phrases.
    text = text.replace(
        "state university of new york",
        "suny",
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    return text


def compact_name(name: str) -> str:

    return re.sub(
        r"[^a-z0-9]",
        "",
        normalize_name(name),
    )


def similarity(
    a: str,
    b: str,
) -> float:

    return SequenceMatcher(
        None,
        normalize_name(a),
        normalize_name(b),
    ).ratio()


def build_id(name: str) -> str:

    text = clean(name).upper()

    text = re.sub(
        r"\([^)]*\)",
        "",
        text,
    )

    text = text.replace(
        "&",
        " AND ",
    )

    text = re.sub(
        r"[^A-Z0-9]+",
        "-",
        text,
    )

    text = re.sub(
        r"-+",
        "-",
        text,
    )

    return (
        "UNI-"
        + text.strip("-")
    )


# ==============================================================
# SPECIAL NAME ALIASES
# ==============================================================

ALIASES = {

    "University of Michigan-Ann Arbor":
        [
            "University of Michigan",
            "University of Michigan Ann Arbor",
        ],

    "University of California, Berkeley (UCB)":
        [
            "University of California Berkeley",
            "University of California, Berkeley",
            "University of California Berkeley",
            "UC Berkeley",
        ],

    "University of California, Los Angeles (UCLA)":
        [
            "University of California Los Angeles",
            "University of California, Los Angeles",
            "UCLA",
        ],

    "University of California, San Diego (UCSD)":
        [
            "University of California San Diego",
            "University of California, San Diego",
            "UC San Diego",
        ],

    "University of California, Santa Barbara (UCSB)":
        [
            "University of California Santa Barbara",
            "University of California, Santa Barbara",
            "UC Santa Barbara",
        ],

    "University at Buffalo SUNY":
        [
            "University at Buffalo",
            "University of Buffalo",
            "SUNY Buffalo",
        ],

    "Stony Brook University, State University of New York":
        [
            "Stony Brook University",
            "Stony Brook",
        ],

    "Binghamton University SUNY":
        [
            "Binghamton University",
            "SUNY Binghamton",
        ],

    "University at Albany SUNY":
        [
            "University at Albany",
            "SUNY Albany",
        ],

    "University of Wisconsin-Madison":
        [
            "University of Wisconsin Madison",
            "University of Wisconsin-Madison",
        ],

    "University of Colorado Denver | Anschutz Medical Campus":
        [
            "University of Colorado Denver",
        ],

    "The New School, New York City and Paris":
        [
            "The New School",
        ],

    "University of Arkansas Fayetteville":
        [
            "University of Arkansas",
        ],

    "University of Missouri, Columbia":
        [
            "University of Missouri",
            "University of Missouri Columbia",
        ],

    "University of Missouri, Kansas City":
        [
            "University of Missouri Kansas City",
            "University of Missouri-Kansas City",
        ],

    "University of Nevada - Reno":
        [
            "University of Nevada Reno",
            "University of Nevada, Reno",
        ],

    "University of Nevada - Las Vegas":
        [
            "University of Nevada Las Vegas",
            "University of Nevada, Las Vegas",
        ],

    "Florida Atlantic University - Boca Raton":
        [
            "Florida Atlantic University",
        ],

    "Indiana University Indianapolis (IU Indianapolis)":
        [
            "Indiana University Indianapolis",
            "IU Indianapolis",
        ],

    "University of Minnesota (System)":
        [
            "University of Minnesota",
        ],

    "The University of Tennessee, Knoxville":
        [
            "University of Tennessee Knoxville",
            "University of Tennessee",
        ],

    "The University of Texas at Arlington":
        [
            "University of Texas at Arlington",
        ],

    "The University of Texas at San Antonio":
        [
            "University of Texas at San Antonio",
            "UT San Antonio",
        ],
}


# ==============================================================
# OBVIOUS SUB-ENTITY FILTER
# ==============================================================

SUBENTITY_WORDS = [
    "college of computing",
    "college of science",
    "college of engineering",
    "school of medicine",
    "school of law",
    "school of business",
    "school of nursing",
    "school of education",
    "board of regents",
    "board of trustees",
    "library",
    "libraries",
    "department of",
    "faculty of",
    "foundation",
    "alumni association",
    "research institute",
]


def looks_like_subentity(
    name: str,
) -> bool:

    text = normalize_name(
        name
    )

    for phrase in SUBENTITY_WORDS:

        if phrase in text:
            return True

    return False


# ==============================================================
# SOURCE DOWNLOAD
# ==============================================================

def download_source() -> list[dict]:

    print()
    print(
        "Downloading university-domain source..."
    )

    response = requests.get(
        SOURCE_URL,
        headers=HEADERS,
        timeout=TIMEOUT,
    )

    response.raise_for_status()

    data = response.json()

    if not isinstance(
        data,
        list,
    ):

        raise ValueError(
            "Unexpected source format."
        )

    print(
        f"Source records downloaded: "
        f"{len(data)}"
    )

    return data


# ==============================================================
# LOAD LOCAL KNOWLEDGE
# ==============================================================

def load_json_registry() -> dict:

    if not REGISTRY_FILE.exists():
        return {}

    with REGISTRY_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(file)


def load_current_output() -> dict:

    if not CURRENT_OUTPUT.exists():
        return {}

    try:

        df = pd.read_csv(
            CURRENT_OUTPUT
        )

    except Exception:
        return {}

    index = {}

    for _, row in df.iterrows():

        name = clean(
            row.get(
                "university_name",
                "",
            )
        )

        status = clean(
            row.get(
                "discovery_status",
                "",
            )
        )

        if (
            name
            and status == "success"
        ):

            index[
                normalize_name(name)
            ] = row.to_dict()

    return index


# ==============================================================
# SOURCE INDEX
# ==============================================================

def build_source_index(
    source_data: list[dict],
) -> tuple[dict, dict]:

    exact_index = {}
    country_index = {}

    for item in source_data:

        name = clean(
            item.get(
                "name",
                "",
            )
        )

        country = clean(
            item.get(
                "country",
                "",
            )
        )

        domains = item.get(
            "domains",
            [],
        )

        web_pages = item.get(
            "web_pages",
            [],
        )

        if not name:
            continue

        record = {
            "name": name,
            "country": country,
            "domains": domains,
            "web_pages": web_pages,
        }

        normalized = normalize_name(
            name
        )

        exact_index[
            normalized
        ] = record

        country_index.setdefault(
            country.lower(),
            [],
        ).append(
            record
        )

    return (
        exact_index,
        country_index,
    )


# ==============================================================
# CANDIDATE MATCHING
# ==============================================================

def candidate_score(
    qs_name: str,
    source_name: str,
) -> float:

    qs_norm = normalize_name(
        qs_name
    )

    source_norm = normalize_name(
        source_name
    )

    # Exact normalized match.
    if qs_norm == source_norm:
        return 1.0

    # Compact match.
    if compact_name(
        qs_name
    ) == compact_name(
        source_name
    ):

        return 0.98

    return similarity(
        qs_name,
        source_name,
    )


def find_best_match(
    qs_name: str,
    usa_records: list[dict],
) -> tuple[dict | None, float]:

    # ----------------------------------------------------------
    # Direct exact match
    # ----------------------------------------------------------

    target = normalize_name(
        qs_name
    )

    for record in usa_records:

        if normalize_name(
            record["name"]
        ) == target:

            return (
                record,
                1.0,
            )

    # ----------------------------------------------------------
    # Alias matching
    # ----------------------------------------------------------

    aliases = ALIASES.get(
        qs_name,
        [],
    )

    for alias in aliases:

        alias_norm = normalize_name(
            alias
        )

        for record in usa_records:

            if normalize_name(
                record["name"]
            ) == alias_norm:

                return (
                    record,
                    0.98,
                )

    # ----------------------------------------------------------
    # Fuzzy matching
    # ----------------------------------------------------------

    best = None
    best_score = 0.0
    second_score = 0.0

    for record in usa_records:

        score = candidate_score(
            qs_name,
            record["name"],
        )

        if score > best_score:

            second_score = best_score
            best_score = score
            best = record

        elif score > second_score:

            second_score = score

    # Require strong separation.
    if (
        best is not None
        and best_score >= 0.88
        and (
            best_score - second_score
            >= 0.03
        )
    ):

        return (
            best,
            best_score,
        )

    return (
        None,
        0.0,
    )


# ==============================================================
# MAIN RESOLUTION
# ==============================================================

def main():

    print()
    print("=" * 70)
    print(
        "UNIVORA - BULK UNIVERSITY RESOLVER v1.0"
    )
    print("=" * 70)
    print()

    # ----------------------------------------------------------
    # Load QS
    # ----------------------------------------------------------

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"Missing QS file:\n"
            f"{INPUT_FILE}"
        )

    qs_df = pd.read_csv(
        INPUT_FILE
    )

    total = len(
        qs_df
    )

    print(
        f"QS universities: {total}"
    )

    # ----------------------------------------------------------
    # Existing data
    # ----------------------------------------------------------

    registry = load_json_registry()

    registry_index = {
        normalize_name(name): record
        for name, record
        in registry.items()
    }

    existing_index = (
        load_current_output()
    )

    print(
        f"Local registry: "
        f"{len(registry_index)}"
    )

    print(
        f"Existing successful output: "
        f"{len(existing_index)}"
    )

    # ----------------------------------------------------------
    # Download Hipo source
    # ----------------------------------------------------------

    source_data = download_source()

    # Only USA records because QS dataset is already the USA list.
    usa_records = [
        item
        for item in source_data
        if clean(
            item.get(
                "country",
                "",
            )
        ).lower()
        in {
            "united states",
            "usa",
            "united states of america",
        }
    ]

    print(
        f"USA source records: "
        f"{len(usa_records)}"
    )

    # ----------------------------------------------------------
    # Resolution
    # ----------------------------------------------------------

    results = []

    reviews = []

    resolved = 0

    local_count = 0

    source_count = 0

    unresolved = 0

    for position, (_, row) in enumerate(
        qs_df.iterrows(),
        start=1,
    ):

        qs_name = clean(
            row.get(
                "university_name",
                "",
            )
        )

        rank = clean(
            row.get(
                "qs_rank_2027",
                "",
            )
        )

        university_id = clean(
            row.get(
                "university_id",
                "",
            )
        )

        if not university_id:

            university_id = build_id(
                qs_name
            )

        print(
            f"[{position}/{total}] "
            f"{qs_name}"
        )

        # ------------------------------------------------------
        # 1. Existing successful record
        # ------------------------------------------------------

        existing = existing_index.get(
            normalize_name(qs_name)
        )

        if existing:

            print(
                "    ✓ existing verified output"
            )

            results.append(
                {
                    "university_id": university_id,
                    "university_name": qs_name,
                    "qs_rank_2027": rank,
                    "official_domain": clean(
                        existing.get(
                            "official_domain",
                            "",
                        )
                    ),
                    "university_website": clean(
                        existing.get(
                            "university_website",
                            "",
                        )
                    ),
                    "confidence": 1.0,
                    "discovery_method": (
                        "existing_verified_output"
                    ),
                    "wikidata_id": clean(
                        existing.get(
                            "wikidata_id",
                            "",
                        )
                    ),
                    "wikidata_label": clean(
                        existing.get(
                            "wikidata_label",
                            "",
                        )
                    ),
                    "website_status": (
                        "not_checked"
                    ),
                    "website_error": "",
                    "discovery_status": (
                        "success"
                    ),
                }
            )

            reviews.append(
                {
                    "university_name": qs_name,
                    "qs_rank_2027": rank,
                    "status": "resolved",
                    "source": (
                        "existing_verified_output"
                    ),
                    "matched_name": (
                        existing.get(
                            "wikidata_label",
                            "",
                        )
                    ),
                    "score": 1.0,
                }
            )

            resolved += 1
            local_count += 1

            continue

        # ------------------------------------------------------
        # 2. Canonical registry
        # ------------------------------------------------------

        registry_record = (
            registry_index.get(
                normalize_name(
                    qs_name
                )
            )
        )

        if registry_record:

            print(
                "    ✓ canonical registry"
            )

            results.append(
                {
                    "university_id": university_id,
                    "university_name": qs_name,
                    "qs_rank_2027": rank,
                    "official_domain": clean(
                        registry_record.get(
                            "official_domain",
                            "",
                        )
                    ),
                    "university_website": clean(
                        registry_record.get(
                            "official_website",
                            "",
                        )
                    ),
                    "confidence": 1.0,
                    "discovery_method": (
                        "canonical_registry"
                    ),
                    "wikidata_id": "",
                    "wikidata_label": clean(
                        registry_record.get(
                            "canonical_name",
                            qs_name,
                        )
                    ),
                    "website_status": (
                        "not_checked"
                    ),
                    "website_error": "",
                    "discovery_status": (
                        "success"
                    ),
                }
            )

            reviews.append(
                {
                    "university_name": qs_name,
                    "qs_rank_2027": rank,
                    "status": "resolved",
                    "source": (
                        "canonical_registry"
                    ),
                    "matched_name": clean(
                        registry_record.get(
                            "canonical_name",
                            qs_name,
                        )
                    ),
                    "score": 1.0,
                }
            )

            resolved += 1
            local_count += 1

            continue

        # ------------------------------------------------------
        # 3. Bulk external domain dataset
        # ------------------------------------------------------

        match, score = find_best_match(
            qs_name,
            usa_records,
        )

        if match is not None:

            domains = match.get(
                "domains",
                [],
            )

            web_pages = match.get(
                "web_pages",
                [],
            )

            # Prefer root registered domains.
            domain = ""

            if domains:

                domain = clean(
                    domains[0]
                )

            website = ""

            if web_pages:

                website = clean(
                    web_pages[0]
                )

            print(
                f"    ✓ bulk source match: "
                f"{match['name']}"
            )

            print(
                f"      domain: {domain}"
            )

            print(
                f"      score: {score:.3f}"
            )

            results.append(
                {
                    "university_id": university_id,
                    "university_name": qs_name,
                    "qs_rank_2027": rank,
                    "official_domain": domain,
                    "university_website": website,
                    "confidence": round(
                        score,
                        3,
                    ),
                    "discovery_method": (
                        "bulk_university_domain_source"
                    ),
                    "wikidata_id": "",
                    "wikidata_label": "",
                    "website_status": (
                        "not_checked"
                    ),
                    "website_error": "",
                    "discovery_status": (
                        "success"
                    ),
                }
            )

            reviews.append(
                {
                    "university_name": qs_name,
                    "qs_rank_2027": rank,
                    "status": "resolved",
                    "source": (
                        "bulk_university_domain_source"
                    ),
                    "matched_name": match[
                        "name"
                    ],
                    "score": round(
                        score,
                        3,
                    ),
                }
            )

            resolved += 1
            source_count += 1

        else:

            print(
                "    ⚠ unresolved"
            )

            results.append(
                {
                    "university_id": university_id,
                    "university_name": qs_name,
                    "qs_rank_2027": rank,
                    "official_domain": "",
                    "university_website": "",
                    "confidence": 0.0,
                    "discovery_method": (
                        "unresolved"
                    ),
                    "wikidata_id": "",
                    "wikidata_label": "",
                    "website_status": (
                        "not_checked"
                    ),
                    "website_error": "",
                    "discovery_status": (
                        "needs_review"
                    ),
                }
            )

            reviews.append(
                {
                    "university_name": qs_name,
                    "qs_rank_2027": rank,
                    "status": (
                        "needs_review"
                    ),
                    "source": "",
                    "matched_name": "",
                    "score": 0.0,
                }
            )

            unresolved += 1

    # ----------------------------------------------------------
    # Save
    # ----------------------------------------------------------

    output_df = pd.DataFrame(
        results
    )

    output_df.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    review_df = pd.DataFrame(
        reviews
    )

    review_df.to_csv(
        REVIEW_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    # ----------------------------------------------------------
    # Summary
    # ----------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "✅ BULK UNIVERSITY RESOLUTION FINISHED"
    )
    print("=" * 70)
    print()

    print(
        f"Processed: {total}"
    )

    print(
        f"Universities identified: {resolved}"
    )

    print(
        f"Local/existing: {local_count}"
    )

    print(
        f"Bulk source: {source_count}"
    )

    print(
        f"Needs review: {unresolved}"
    )

    print()

    print(
        "Output:"
    )

    print(
        OUTPUT_FILE
    )

    print()

    print(
        "Review:"
    )

    print(
        REVIEW_FILE
    )

    print()


if __name__ == "__main__":
    main()