# =====================================================
# DATA CLEANING
# TIER 3 - AODS 8
# =====================================================

from typing import List


def clean_data(
    records: List[str]
) -> List[str]:

    cleaned = []

    for record in records or []:

        value = str(
            record
        ).strip()

        if not value:

            continue

        if value.lower() in [

            "none",
            "null",
            "n/a"

        ]:

            continue

        cleaned.append(
            value
        )

    return cleaned


if __name__ == "__main__":

    sample = [

        " Memory ",

        "",

        "Research",

        "null",

        "Wisdom",

        "N/A",

        "Patterns"

    ]

    result = clean_data(
        sample
    )

    print(result)

    assert len(result) == 4

    assert "Memory" in result

    assert "Wisdom" in result

