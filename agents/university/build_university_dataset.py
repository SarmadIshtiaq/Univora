"""
Univora - QS 2027 University Dataset Builder
=============================================

Reads the QS World University Rankings 2027 Excel file.

The actual QS spreadsheet structure is:

2027 | 2026 | Institution | Location | Classification | ...

Therefore:

    Institution -> university name
    Location    -> country/location
    2027        -> QS 2027 rank

Output:
    data/processed/universities_usa.csv
"""

from pathlib import Path
import re
import sys

import pandas as pd


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "external"
    / "2027_QS_World_University_Rankings_1_3__For_qs_com_.xlsx"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "universities_usa.csv"
)


# ============================================================
# HELPERS
# ============================================================

def clean_text(value) -> str:
    """Convert a spreadsheet value into clean text."""

    if pd.isna(value):
        return ""

    text = str(value).strip()

    text = text.replace("\n", " ")

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text


def normalize_name(value) -> str:
    """Normalize university name for duplicate checking."""

    text = clean_text(value).lower()

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def create_university_id(
    university_name: str,
    number: int,
) -> str:
    """Create readable university ID."""

    text = clean_text(
        university_name
    ).upper()

    text = re.sub(
        r"[^A-Z0-9]+",
        "-",
        text,
    )

    text = text.strip("-")

    if not text:
        return f"UNI-{number:04d}"

    return f"UNI-{text}"


# ============================================================
# LOAD QS FILE
# ============================================================

def load_qs_file() -> pd.DataFrame:

    print("=" * 70)
    print("UNIVORA - QS 2027 UNIVERSITY DATA PIPELINE")
    print("=" * 70)

    print("\n[1/6] Checking QS file...")

    if not INPUT_FILE.exists():

        print("\n❌ QS file not found.")

        print("\nExpected file:")
        print(INPUT_FILE)

        sys.exit(1)

    print("✓ File found")
    print(INPUT_FILE)

    # --------------------------------------------------------
    # Read raw spreadsheet first.
    # --------------------------------------------------------

    print(
        "\n[2/6] Reading spreadsheet..."
    )

    try:

        raw = pd.read_excel(
            INPUT_FILE,
            header=None,
            engine="openpyxl",
        )

    except Exception as error:

        print(
            "\n❌ Could not read Excel file."
        )

        print(
            f"{type(error).__name__}: {error}"
        )

        sys.exit(1)

    print("✓ Excel file loaded")

    print(
        f"  Rows: {len(raw):,}"
    )

    print(
        f"  Columns: {len(raw.columns)}"
    )

    return raw


# ============================================================
# FIND HEADER ROW
# ============================================================

def find_header_row(
    raw: pd.DataFrame,
) -> int | None:

    print(
        "\n[3/6] Finding QS table header..."
    )

    # The QS file should contain "Institution"
    # and "Location" in the same row.

    for row_number in range(
        min(30, len(raw))
    ):

        values = [
            clean_text(value).lower()
            for value in raw.iloc[row_number]
        ]

        has_institution = (
            "institution" in values
        )

        has_location = (
            "location" in values
        )

        has_rank_2027 = (
            "2027" in values
        )

        if (
            has_institution
            and has_location
            and has_rank_2027
        ):

            print(
                f"✓ QS header found at Excel row "
                f"{row_number + 1}"
            )

            print(
                "  Columns found:"
            )

            for value in raw.iloc[
                row_number
            ].dropna():

                print(
                    f"    - {value}"
                )

            return row_number

    print(
        "\n❌ Could not find the QS header row."
    )

    print(
        "\nFirst 15 spreadsheet rows:"
    )

    print(
        raw.iloc[
            :15,
            :15
        ].to_string(
            index=True,
            header=False,
        )
    )

    return None


# ============================================================
# LOAD TABLE
# ============================================================

def load_table(
    raw: pd.DataFrame,
) -> pd.DataFrame:

    header_row = find_header_row(
        raw
    )

    if header_row is None:

        sys.exit(1)

    dataframe = pd.read_excel(
        INPUT_FILE,
        header=header_row,
        engine="openpyxl",
    )

    # Clean column names.
    dataframe.columns = [
        clean_text(column)
        for column in dataframe.columns
    ]

    print(
        "\n[4/6] QS table loaded."
    )

    print(
        "\nImportant columns:"
    )

    for column in dataframe.columns:
        print(
            f"  - {column}"
        )

    return dataframe


# ============================================================
# VALIDATE COLUMNS
# ============================================================

def validate_columns(
    dataframe: pd.DataFrame,
):

    required = [
        "2027",
        "Institution",
        "Location",
    ]

    missing = [
        column
        for column in required
        if column not in dataframe.columns
    ]

    if missing:

        print(
            "\n❌ Required QS columns missing:"
        )

        for column in missing:
            print(
                f"  - {column}"
            )

        print(
            "\nAvailable columns:"
        )

        for column in dataframe.columns:
            print(
                f"  - {column}"
            )

        sys.exit(1)

    print(
        "\n✓ Required QS columns confirmed"
    )


# ============================================================
# FILTER USA
# ============================================================

def filter_usa(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:

    print(
        "\n[5/6] Filtering United States universities..."
    )

    working = dataframe.copy()

    # Clean location.
    working["_location_clean"] = (
        working["Location"]
        .apply(clean_text)
        .str.lower()
    )

    # The QS spreadsheet uses Location.
    #
    # We search for "United States" rather than expecting
    # an exact country column.

    usa_mask = (
        working["_location_clean"]
        .str.contains(
            "united states",
            case=False,
            na=False,
        )
    )

    usa = working[
        usa_mask
    ].copy()

    print(
        f"✓ USA records found: "
        f"{len(usa):,}"
    )

    if usa.empty:

        print(
            "\n❌ No United States universities found."
        )

        print(
            "\nLocation examples:"
        )

        print(
            working["Location"]
            .dropna()
            .astype(str)
            .value_counts()
            .head(30)
            .to_string()
        )

        sys.exit(1)

    return usa


# ============================================================
# BUILD FINAL DATASET
# ============================================================

def build_dataset(
    usa: pd.DataFrame,
) -> pd.DataFrame:

    print(
        "\n[6/6] Cleaning and building dataset..."
    )

    result = pd.DataFrame()

    # --------------------------------------------------------
    # University name
    # --------------------------------------------------------

    result["university_name"] = (
        usa["Institution"]
        .apply(clean_text)
    )

    # --------------------------------------------------------
    # Country
    # --------------------------------------------------------

    result["country"] = (
        "United States"
    )

    # --------------------------------------------------------
    # Location
    # --------------------------------------------------------

    result["location"] = (
        usa["Location"]
        .apply(clean_text)
    )

    # --------------------------------------------------------
    # QS 2027 Rank
    # --------------------------------------------------------

    result["qs_rank_2027"] = (
        usa["2027"]
        .apply(clean_text)
    )

    # --------------------------------------------------------
    # Remove blank names
    # --------------------------------------------------------

    result = result[
        result["university_name"] != ""
    ].copy()

    # --------------------------------------------------------
    # Remove duplicates
    # --------------------------------------------------------

    result["_normalized_name"] = (
        result["university_name"]
        .apply(normalize_name)
    )

    result = (
        result
        .drop_duplicates(
            subset="_normalized_name",
            keep="first",
        )
        .copy()
    )

    result = result.drop(
        columns="_normalized_name"
    )

    # --------------------------------------------------------
    # Create IDs
    # --------------------------------------------------------

    ids = []

    for index, university_name in enumerate(
        result["university_name"],
        start=1,
    ):

        ids.append(
            create_university_id(
                university_name,
                index,
            )
        )

    result.insert(
        0,
        "university_id",
        ids,
    )

    # --------------------------------------------------------
    # Official domain
    # --------------------------------------------------------
    #
    # This will be discovered later by the
    # University Agent.
    #

    result["official_domain"] = ""

    # --------------------------------------------------------
    # Source
    # --------------------------------------------------------

    result["ranking_source"] = (
        "QS World University Rankings 2027"
    )

    result["source_file"] = (
        INPUT_FILE.name
    )

    # --------------------------------------------------------
    # Final column order
    # --------------------------------------------------------

    result = result[
        [
            "university_id",
            "university_name",
            "country",
            "location",
            "qs_rank_2027",
            "official_domain",
            "ranking_source",
            "source_file",
        ]
    ]

    print(
        f"\n✓ Clean USA universities: "
        f"{len(result):,}"
    )

    return result


# ============================================================
# SAVE DATASET
# ============================================================

def save_dataset(
    dataframe: pd.DataFrame,
):

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    dataframe.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        "\n✓ Dataset saved successfully"
    )

    print(
        OUTPUT_FILE
    )


# ============================================================
# MAIN
# ============================================================

def main():

    raw = load_qs_file()

    dataframe = load_table(
        raw
    )

    validate_columns(
        dataframe
    )

    usa = filter_usa(
        dataframe
    )

    result = build_dataset(
        usa
    )

    save_dataset(
        result
    )

    print(
        "\n" + "=" * 70
    )

    print(
        "✅ UNIVORA UNIVERSITY DATASET COMPLETE"
    )

    print(
        "=" * 70
    )

    print(
        f"\nTotal USA universities: "
        f"{len(result):,}"
    )

    print(
        "\nFirst 20 universities:"
    )

    print(
        result[
            [
                "university_id",
                "university_name",
                "qs_rank_2027",
            ]
        ]
        .head(20)
        .to_string(
            index=False
        )
    )

    print(
        "\nOutput:"
    )

    print(
        OUTPUT_FILE
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()