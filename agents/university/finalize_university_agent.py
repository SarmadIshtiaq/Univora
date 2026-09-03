from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict

import pandas as pd


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

QS_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "universities_usa.csv"
)

EXISTING_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "university_sources.csv"
)

BULK_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "university_sources_bulk.csv"
)

REGISTRY_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "university_registry.json"
)

FINAL_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "university_sources_final.csv"
)

REVIEW_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "university_review_final.csv"
)


# ============================================================
# OUTPUT SCHEMA
# ============================================================

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


REVIEW_COLUMNS = [
    "university_name",
    "qs_rank_2027",
    "status",
    "reason",
    "source",
    "matched_name",
    "official_domain",
    "official_website",
    "confidence",
]


# ============================================================
# HELPERS
# ============================================================

def clean(value: Any) -> str:
    """
    Convert a value into clean text.
    """

    if value is None:
        return ""

    text = str(value).strip()

    if text.lower() in {
        "",
        "nan",
        "none",
    }:
        return ""

    return text


def normalize_name(name: str) -> str:
    """
    Normalize university names for matching.
    """

    text = clean(name).lower()

    # Unicode punctuation.
    text = text.replace("’", "'")
    text = text.replace("–", "-")
    text = text.replace("—", "-")

    # Ampersand.
    text = text.replace("&", " and ")

    # Remove parenthetical abbreviations.
    text = re.sub(
        r"\([^)]*\)",
        "",
        text,
    )

    # Normalize separators.
    text = re.sub(
        r"[/|,;:]+",
        " ",
        text,
    )

    # Normalize hyphens.
    text = re.sub(
        r"-+",
        " ",
        text,
    )

    # Remove leading "the".
    text = re.sub(
        r"^\s*the\s+",
        "",
        text,
    )

    # Collapse spaces.
    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    # Known naming equivalences.
    replacements = {
        "university of michigan ann arbor":
            "university of michigan",

        "university of michigan":
            "university of michigan",

        "university of wisconsin madison":
            "university of wisconsin madison",

        "university at buffalo suny":
            "university at buffalo",

        "university at buffalo":
            "university at buffalo",

        "stony brook university state university of new york":
            "stony brook university",

        "binghamton university suny":
            "binghamton university",

        "university at albany suny":
            "university at albany",

        "university of nebraska lincoln":
            "university of nebraska lincoln",

        "university of arkansas fayetteville":
            "university of arkansas",

        "university of nevada reno":
            "university of nevada reno",

        "university of nevada las vegas":
            "university of nevada las vegas",

        "florida atlantic university boca raton":
            "florida atlantic university",

        "the new school new york city and paris":
            "the new school",

        "university of colorado denver anschutz medical campus":
            "university of colorado denver",

        "indiana university indianapolis iu indianapolis":
            "indiana university indianapolis",

        "university of missouri columbia":
            "university of missouri",

        "university of missouri kansas city":
            "university of missouri kansas city",

        "university of wisconsin milwaukee":
            "university of wisconsin milwaukee",

        "university of california berkeley":
            "university of california berkeley",

        "university of california los angeles":
            "university of california los angeles",

        "university of california san diego":
            "university of california san diego",

        "university of california santa barbara":
            "university of california santa barbara",
    }

    return replacements.get(
        text,
        text,
    )


def build_university_id(
    name: str,
) -> str:

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

    text = text.replace(
        "’",
        "'",
    )

    text = text.replace(
        "–",
        "-",
    )

    text = text.replace(
        "—",
        "-",
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

    return (
        f"UNI-{text}"
    )


def has_complete_source(
    record: Dict[str, Any],
) -> bool:
    """
    A source is usable only when both domain
    and website are present.
    """

    domain = clean(
        record.get(
            "official_domain",
            "",
        )
    )

    website = clean(
        record.get(
            "university_website",
            "",
        )
    )

    return bool(
        domain
        and website
    )


# ============================================================
# CSV LOADERS
# ============================================================

def load_csv(
    path: Path,
) -> pd.DataFrame:

    if not path.exists():
        return pd.DataFrame()

    try:

        return pd.read_csv(
            path
        )

    except Exception as exc:

        print(
            f"⚠ Could not read {path}: "
            f"{exc}"
        )

        return pd.DataFrame()


def index_dataframe(
    df: pd.DataFrame,
) -> Dict[str, Dict[str, Any]]:
    """
    Index records by normalized university name.
    """

    index: Dict[
        str,
        Dict[str, Any]
    ] = {}

    if df.empty:
        return index

    if (
        "university_name"
        not in df.columns
    ):
        return index

    for _, row in df.iterrows():

        name = clean(
            row.get(
                "university_name",
                "",
            )
        )

        if not name:
            continue

        index[
            normalize_name(name)
        ] = row.to_dict()

    return index


# ============================================================
# REGISTRY
# ============================================================

def load_registry() -> Dict[str, Any]:

    if not REGISTRY_FILE.exists():
        return {}

    try:

        with REGISTRY_FILE.open(
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(
                file
            )

        if not isinstance(
            data,
            dict,
        ):
            return {}

        return data

    except Exception as exc:

        print(
            f"⚠ Could not read registry: "
            f"{exc}"
        )

        return {}


def index_registry(
    registry: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:

    index = {}

    for name, record in registry.items():

        if not isinstance(
            record,
            dict,
        ):
            continue

        index[
            normalize_name(name)
        ] = record

    return index


# ============================================================
# SOURCE SELECTION
# ============================================================

def select_existing_source(
    name: str,
    existing_index: Dict[str, Dict[str, Any]],
) -> Dict[str, Any] | None:

    record = existing_index.get(
        normalize_name(name)
    )

    if not record:
        return None

    if not has_complete_source(
        record
    ):
        return None

    return record


def select_registry_source(
    name: str,
    registry_index: Dict[str, Dict[str, Any]],
) -> Dict[str, Any] | None:

    record = registry_index.get(
        normalize_name(name)
    )

    if not record:
        return None

    domain = clean(
        record.get(
            "official_domain",
            "",
        )
    )

    website = clean(
        record.get(
            "official_website",
            "",
        )
    )

    if not (
        domain
        and website
    ):
        return None

    return record


def select_bulk_source(
    name: str,
    bulk_index: Dict[str, Dict[str, Any]],
) -> Dict[str, Any] | None:

    record = bulk_index.get(
        normalize_name(name)
    )

    if not record:
        return None

    status = clean(
        record.get(
            "discovery_status",
            "",
        )
    )

    if status != "success":
        return None

    if not has_complete_source(
        record
    ):
        return None

    return record


# ============================================================
# BUILD FINAL RECORD
# ============================================================

def make_final_record(
    qs_row: Dict[str, Any],
    source: Dict[str, Any],
    source_name: str,
) -> Dict[str, Any]:

    name = clean(
        qs_row.get(
            "university_name",
            "",
        )
    )

    rank = clean(
        qs_row.get(
            "qs_rank_2027",
            "",
        )
    )

    university_id = clean(
        qs_row.get(
            "university_id",
            "",
        )
    )

    if not university_id:

        university_id = (
            build_university_id(
                name
            )
        )

    wikidata_id = clean(
        source.get(
            "wikidata_id",
            "",
        )
    )

    wikidata_label = clean(
        source.get(
            "wikidata_label",
            "",
        )
    )

    canonical_name = clean(
        source.get(
            "canonical_name",
            "",
        )
    )

    if not wikidata_label:
        wikidata_label = (
            canonical_name
            or name
        )

    domain = clean(
        source.get(
            "official_domain",
            "",
        )
    )

    website = clean(
        source.get(
            "official_website",
            source.get(
                "university_website",
                "",
            ),
        )
    )

    # --------------------------------------------------------
    # Confidence
    # --------------------------------------------------------

    if source_name in {
        "existing_verified_output",
        "canonical_registry",
    }:

        confidence = 1.0

    else:

        raw_confidence = clean(
            source.get(
                "confidence",
                "",
            )
        )

        try:

            confidence = float(
                raw_confidence
            )

        except (
            ValueError,
            TypeError,
        ):

            confidence = 0.95

    return {
        "university_id": university_id,
        "university_name": name,
        "qs_rank_2027": rank,
        "official_domain": domain,
        "university_website": website,
        "confidence": confidence,
        "discovery_method": source_name,
        "wikidata_id": wikidata_id,
        "wikidata_label": wikidata_label,
        "website_status": "not_checked",
        "website_error": "",
        "discovery_status": "success",
    }


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 72)
    print(
        "UNIVORA - UNIVERSITY FINALIZER v1.1"
    )
    print("=" * 72)
    print()

    # ---------------------------------------------------------
    # Load QS
    # ---------------------------------------------------------

    qs_df = load_csv(
        QS_FILE
    )

    if qs_df.empty:

        raise RuntimeError(
            "QS university dataset is empty."
        )

    # ---------------------------------------------------------
    # Load all available sources
    # ---------------------------------------------------------

    existing_df = load_csv(
        EXISTING_FILE
    )

    bulk_df = load_csv(
        BULK_FILE
    )

    registry = load_registry()

    existing_index = index_dataframe(
        existing_df
    )

    bulk_index = index_dataframe(
        bulk_df
    )

    registry_index = index_registry(
        registry
    )

    print(
        f"QS universities: "
        f"{len(qs_df)}"
    )

    print(
        f"Existing output records: "
        f"{len(existing_index)}"
    )

    print(
        f"Bulk resolver records: "
        f"{len(bulk_index)}"
    )

    print(
        f"Canonical registry records: "
        f"{len(registry_index)}"
    )

    print()

    # ---------------------------------------------------------
    # Final records
    # ---------------------------------------------------------

    final_records = []

    review_records = []

    existing_count = 0
    registry_count = 0
    bulk_count = 0
    unresolved_count = 0

    # ---------------------------------------------------------
    # Process every QS university
    # ---------------------------------------------------------

    for position, (_, qs_row) in enumerate(
        qs_df.iterrows(),
        start=1,
    ):

        name = clean(
            qs_row.get(
                "university_name",
                "",
            )
        )

        rank = clean(
            qs_row.get(
                "qs_rank_2027",
                "",
            )
        )

        print(
            f"[{position}/{len(qs_df)}] "
            f"{name}"
        )

        # =====================================================
        # PRIORITY 1
        # Existing verified output
        #
        # IMPORTANT:
        # Only use this source if it has both domain
        # and website.
        # =====================================================

        source = select_existing_source(
            name,
            existing_index,
        )

        if source:

            print(
                "    ✓ existing verified"
            )

            final_records.append(
                make_final_record(
                    qs_row.to_dict(),
                    source,
                    "existing_verified_output",
                )
            )

            existing_count += 1

            continue

        # =====================================================
        # PRIORITY 2
        # Canonical registry
        # =====================================================

        source = select_registry_source(
            name,
            registry_index,
        )

        if source:

            print(
                "    ✓ canonical registry"
            )

            final_records.append(
                make_final_record(
                    qs_row.to_dict(),
                    source,
                    "canonical_registry",
                )
            )

            registry_count += 1

            continue

        # =====================================================
        # PRIORITY 3
        # Bulk source
        # =====================================================

        source = select_bulk_source(
            name,
            bulk_index,
        )

        if source:

            print(
                "    ✓ bulk source"
            )

            final_records.append(
                make_final_record(
                    qs_row.to_dict(),
                    source,
                    "bulk_university_domain_source",
                )
            )

            bulk_count += 1

            continue

        # =====================================================
        # UNRESOLVED
        # =====================================================

        print(
            "    ⚠ needs review"
        )

        qs_dict = qs_row.to_dict()

        university_id = clean(
            qs_dict.get(
                "university_id",
                "",
            )
        )

        if not university_id:

            university_id = (
                build_university_id(
                    name
                )
            )

        final_records.append(
            {
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
        )

        review_records.append(
            {
                "university_name": name,
                "qs_rank_2027": rank,
                "status": "needs_review",
                "reason": (
                    "No complete source with "
                    "official domain and website."
                ),
                "source": "",
                "matched_name": "",
                "official_domain": "",
                "official_website": "",
                "confidence": 0.0,
            }
        )

        unresolved_count += 1

    # =========================================================
    # BUILD DATAFRAMES
    # =========================================================

    final_df = pd.DataFrame(
        final_records
    )

    for column in OUTPUT_COLUMNS:

        if column not in final_df.columns:
            final_df[column] = ""

    final_df = final_df[
        OUTPUT_COLUMNS
    ]

    # =========================================================
    # INTEGRITY CHECK BEFORE SAVING
    # =========================================================

    # One row per QS university.
    duplicate_ids = int(
        final_df[
            "university_id"
        ].duplicated()
        .sum()
    )

    duplicate_names = int(
        final_df[
            "university_name"
        ]
        .map(normalize_name)
        .duplicated()
        .sum()
    )

    blank_domains = int(
        final_df[
            "official_domain"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("")
        .sum()
    )

    blank_websites = int(
        final_df[
            "university_website"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("")
        .sum()
    )

    successful = int(
        (
            final_df[
                "discovery_status"
            ]
            == "success"
        )
        .sum()
    )

    # =========================================================
    # SAVE
    # =========================================================

    FINAL_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    final_df.to_csv(
        FINAL_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    review_df = pd.DataFrame(
        review_records,
        columns=REVIEW_COLUMNS,
    )

    review_df.to_csv(
        REVIEW_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    # =========================================================
    # SUMMARY
    # =========================================================

    print()
    print("=" * 72)
    print(
        "✅ UNIVERSITY FINALIZATION COMPLETE"
    )
    print("=" * 72)
    print()

    print(
        f"Processed: {len(qs_df)}"
    )

    print(
        f"Universities identified: {successful}"
    )

    print(
        f"From existing verified: "
        f"{existing_count}"
    )

    print(
        f"From canonical registry: "
        f"{registry_count}"
    )

    print(
        f"From bulk resolver: "
        f"{bulk_count}"
    )

    print(
        f"Needs review: "
        f"{unresolved_count}"
    )

    print()

    print(
        "Integrity check:"
    )

    print(
        f"  Rows: {len(final_df)}"
    )

    print(
        f"  Duplicate IDs: {duplicate_ids}"
    )

    print(
        f"  Duplicate names: {duplicate_names}"
    )

    print(
        f"  Blank domains: {blank_domains}"
    )

    print(
        f"  Blank websites: {blank_websites}"
    )

    print()

    print(
        "Final output:"
    )

    print(
        FINAL_FILE
    )

    print()

    print(
        "Review output:"
    )

    print(
        REVIEW_FILE
    )

    print()


if __name__ == "__main__":
    main()