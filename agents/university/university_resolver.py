"""
UNIVORA - UNIVERSITY RESOLVER

Resolution priority:

1. Verified local university knowledge
2. Existing university output/cache
3. External Wikidata discovery

The resolver is deliberately separate from website-health checking.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

VERIFIED_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "verified_universities.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "university_sources.csv"
)


def normalize_name(name: str) -> str:
    """
    Normalize a university name for local matching.
    """

    text = str(name).strip().lower()

    text = (
        text
        .replace("’", "'")
        .replace("–", "-")
        .replace("—", "-")
    )

    text = text.replace(
        "&",
        " and "
    )

    # Remove parenthetical abbreviations.
    import re

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
        flags=re.I,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    return text


def load_verified_universities() -> Dict[str, Any]:
    """
    Load locally verified university records.
    """

    if not VERIFIED_FILE.exists():
        return {}

    with VERIFIED_FILE.open(
        "r",
        encoding="utf-8",
    ) as f:

        return json.load(f)


def build_normalized_index(
    verified: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """
    Create normalized-name lookup.
    """

    index = {}

    for name, record in verified.items():

        normalized = normalize_name(
            name
        )

        index[
            normalized
        ] = record

    return index


def load_existing_output() -> Dict[str, Dict]:
    """
    Load existing university_sources.csv
    and index successful records.
    """

    if not OUTPUT_FILE.exists():
        return {}

    try:

        df = pd.read_csv(
            OUTPUT_FILE
        )

    except Exception:
        return {}

    index = {}

    for _, row in df.iterrows():

        name = str(
            row.get(
                "university_name",
                "",
            )
        ).strip()

        status = str(
            row.get(
                "discovery_status",
                "",
            )
        ).strip()

        if (
            name
            and status == "success"
        ):

            index[
                normalize_name(name)
            ] = {
                "wikidata_id": row.get(
                    "wikidata_id",
                    "",
                ),
                "wikidata_label": row.get(
                    "wikidata_label",
                    "",
                ),
                "official_domain": row.get(
                    "official_domain",
                    "",
                ),
                "official_website": row.get(
                    "university_website",
                    "",
                ),
                "source": "existing_output",
            }

    return index


def resolve_locally(
    university_name: str,
) -> Optional[Dict[str, Any]]:
    """
    Resolve from verified local knowledge first.
    """

    verified = (
        load_verified_universities()
    )

    index = build_normalized_index(
        verified
    )

    normalized = normalize_name(
        university_name
    )

    # Direct match.
    if normalized in index:

        result = dict(
            index[normalized]
        )

        result[
            "resolution_source"
        ] = "verified_local"

        return result

    # Try existing generated output.
    existing = load_existing_output()

    if normalized in existing:

        result = dict(
            existing[normalized]
        )

        result[
            "resolution_source"
        ] = "existing_output"

        return result

    return None


def print_resolution(
    university_name: str,
    result: Dict[str, Any],
) -> None:

    print()
    print(
        f"✓ Local resolution: "
        f"{university_name}"
    )

    print(
        f"  Source: "
        f"{result.get('resolution_source')}"
    )

    print(
        f"  Wikidata: "
        f"{result.get('wikidata_id')}"
    )

    print(
        f"  University: "
        f"{result.get('wikidata_label')}"
    )

    print(
        f"  Website: "
        f"{result.get('official_website')}"
    )


def main() -> None:

    universities = [
        "California Institute of Technology (Caltech)",
        "Cornell University",
        "Yale University",
        "Johns Hopkins University",
        "University of California, Berkeley (UCB)",
        "University of Chicago",
        "University of California, Los Angeles (UCLA)",
        "University of Michigan-Ann Arbor",
        "Carnegie Mellon University",
        "New York University (NYU)",
        "Brown University",
        "Duke University",
        "University of Texas at Austin",
    ]

    print()
    print("=" * 70)
    print(
        "UNIVORA - LOCAL UNIVERSITY RESOLVER TEST"
    )
    print("=" * 70)

    resolved = 0

    for name in universities:

        result = resolve_locally(
            name
        )

        if result:

            resolved += 1

            print_resolution(
                name,
                result,
            )

        else:

            print()
            print(
                f"⚠ Not in local knowledge: "
                f"{name}"
            )

    print()
    print("=" * 70)
    print(
        f"Resolved locally: "
        f"{resolved}/{len(universities)}"
    )
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()