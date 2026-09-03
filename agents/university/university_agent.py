from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "universities_usa.csv"
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
    / "university_sources.csv"
)

REVIEW_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "university_review.csv"
)


OUTPUT_COLUMNS = [
    "university_id",
    "university_name",
    "qs_rank_2027",
    "official_domain",
    "university_website",
    "confidence",
    "discovery_method",
    "wikidata_id",
    "wikidata_label",
    "website_status",
    "website_error",
    "discovery_status",
]


def clean(value) -> str:
    if value is None:
        return ""

    value = str(value).strip()

    if value.lower() == "nan":
        return ""

    return value


def normalize_name(name: str) -> str:

    text = clean(name).lower()

    text = text.replace("’", "'")
    text = text.replace("–", "-")
    text = text.replace("—", "-")
    text = text.replace("&", " and ")

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

    text = re.sub(
        r"^\s*the\s+",
        "",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    return text


def build_university_id(
    university_name: str,
) -> str:

    text = clean(
        university_name
    ).upper()

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

    text = text.strip("-")

    return f"UNI-{text}"


def load_registry():

    if not REGISTRY_FILE.exists():

        raise FileNotFoundError(
            f"Registry not found:\n"
            f"{REGISTRY_FILE}"
        )

    with REGISTRY_FILE.open(
        "r",
        encoding="utf-8",
    ) as file:

        return json.load(file)


def create_registry_index(
    registry,
):

    index = {}

    for name, record in registry.items():

        index[
            normalize_name(name)
        ] = record

    return index


def create_existing_index():

    index = {}

    if not OUTPUT_FILE.exists():

        return index

    try:

        df = pd.read_csv(
            OUTPUT_FILE
        )

    except Exception:

        return index

    if "university_name" not in df.columns:

        return index

    for _, row in df.iterrows():

        name = clean(
            row.get(
                "university_name",
                "",
            )
        )

        domain = clean(
            row.get(
                "official_domain",
                "",
            )
        )

        website = clean(
            row.get(
                "university_website",
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
            and domain
            and status == "success"
        ):

            index[
                normalize_name(name)
            ] = {
                "canonical_name": clean(
                    row.get(
                        "wikidata_label",
                        "",
                    )
                ) or name,
                "official_domain": domain,
                "official_website": website,
                "wikidata_id": clean(
                    row.get(
                        "wikidata_id",
                        "",
                    )
                ),
                "wikidata_label": clean(
                    row.get(
                        "wikidata_label",
                        "",
                    )
                ),
                "source": "existing_verified_output",
            }

    return index


def resolve(
    university_name,
    registry_index,
    existing_index,
):

    normalized = normalize_name(
        university_name
    )

    # -------------------------------------------------------------
    # 1. Canonical local registry
    # -------------------------------------------------------------

    if normalized in registry_index:

        record = dict(
            registry_index[
                normalized
            ]
        )

        record[
            "resolution_source"
        ] = "canonical_registry"

        return record

    # -------------------------------------------------------------
    # 2. Existing verified output
    # -------------------------------------------------------------

    if normalized in existing_index:

        record = dict(
            existing_index[
                normalized
            ]
        )

        record[
            "resolution_source"
        ] = "existing_output"

        return record

    return None


def build_record(
    row,
    resolved,
):

    name = clean(
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

        university_id = build_university_id(
            name
        )

    if resolved is None:

        return {
            "university_id": university_id,
            "university_name": name,
            "qs_rank_2027": rank,
            "official_domain": "",
            "university_website": "",
            "confidence": 0.0,
            "discovery_method": "unresolved",
            "wikidata_id": "",
            "wikidata_label": "",
            "website_status": "not_checked",
            "website_error": "",
            "discovery_status": "needs_review",
        }

    source = resolved.get(
        "resolution_source",
        "",
    )

    if source == "canonical_registry":

        confidence = 1.0
        method = "canonical_registry"

    elif source == "existing_output":

        confidence = 1.0
        method = "existing_verified_output"

    else:

        confidence = 0.0
        method = "unknown"

    return {
        "university_id": university_id,

        "university_name": name,

        "qs_rank_2027": rank,

        "official_domain": clean(
            resolved.get(
                "official_domain",
                "",
            )
        ),

        "university_website": clean(
            resolved.get(
                "official_website",
                "",
            )
        ),

        "confidence": confidence,

        "discovery_method": method,

        "wikidata_id": clean(
            resolved.get(
                "wikidata_id",
                "",
            )
        ),

        "wikidata_label": clean(
            resolved.get(
                "wikidata_label",
                resolved.get(
                    "canonical_name",
                    "",
                ),
            )
        ),

        "website_status": "not_checked",

        "website_error": "",

        "discovery_status": "success",
    }


def save_output(
    records,
    reviews,
):

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_df = pd.DataFrame(
        records
    )

    output_df = output_df[
        OUTPUT_COLUMNS
    ]

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


def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
    )

    args = parser.parse_args()

    if not INPUT_FILE.exists():

        raise FileNotFoundError(
            f"QS dataset not found:\n"
            f"{INPUT_FILE}"
        )

    df = pd.read_csv(
        INPUT_FILE
    )

    if args.limit:

        df = df.head(
            args.limit
        )

    registry = load_registry()

    registry_index = (
        create_registry_index(
            registry
        )
    )

    existing_index = (
        create_existing_index()
    )

    total = len(df)

    records = []

    reviews = []

    resolved_count = 0

    review_count = 0

    registry_count = 0

    existing_count = 0

    print()
    print("=" * 70)
    print(
        "UNIVORA - UNIVERSITY DISCOVERY AGENT"
    )
    print(
        "FINAL DETERMINISTIC REGISTRY VERSION"
    )
    print("=" * 70)
    print()

    print(
        f"Universities to process: {total}"
    )

    print(
        f"Canonical registry records: "
        f"{len(registry_index)}"
    )

    print()

    for position, (_, row) in enumerate(
        df.iterrows(),
        start=1,
    ):

        name = clean(
            row.get(
                "university_name",
                "",
            )
        )

        print(
            f"[{position}/{total}] "
            f"{name}"
        )

        resolved = resolve(
            name,
            registry_index,
            existing_index,
        )

        if resolved:

            resolved_count += 1

            source = resolved.get(
                "resolution_source"
            )

            if source == "canonical_registry":

                registry_count += 1

            elif source == "existing_output":

                existing_count += 1

            print(
                f"    ✓ "
                f"{resolved.get('canonical_name', name)}"
            )

            print(
                f"    Domain: "
                f"{resolved.get('official_domain', '')}"
            )

        else:

            review_count += 1

            print(
                "    ⚠ NEEDS REVIEW"
            )

        record = build_record(
            row,
            resolved,
        )

        review = {
            "university_name": name,
            "qs_rank_2027": clean(
                row.get(
                    "qs_rank_2027",
                    "",
                )
            ),
            "status": (
                "resolved"
                if resolved
                else "needs_review"
            ),
            "resolution_source": (
                resolved.get(
                    "resolution_source",
                    "",
                )
                if resolved
                else ""
            ),
            "official_domain": (
                resolved.get(
                    "official_domain",
                    "",
                )
                if resolved
                else ""
            ),
            "official_website": (
                resolved.get(
                    "official_website",
                    "",
                )
                if resolved
                else ""
            ),
        }

        records.append(
            record
        )

        reviews.append(
            review
        )

        # Save continuously.
        save_output(
            records,
            reviews,
        )

    print()
    print("=" * 70)
    print(
        "✅ UNIVERSITY DISCOVERY FINISHED"
    )
    print("=" * 70)
    print()

    print(
        f"Processed: {total}"
    )

    print(
        f"Universities identified: "
        f"{resolved_count}"
    )

    print(
        f"Resolved from canonical registry: "
        f"{registry_count}"
    )

    print(
        f"Reused existing verified output: "
        f"{existing_count}"
    )

    print(
        f"Needs review: "
        f"{review_count}"
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