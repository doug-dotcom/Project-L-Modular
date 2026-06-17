# =====================================================
# DATA DEDUPLICATION
# TIER 3 - AODS 9
# =====================================================

from typing import List


def deduplicate_data(
    records: List[str]
) -> List[str]:

    seen = set()

    deduplicated = []

    for record in records or []:

        value = str(
            record
        ).strip()

        if value in seen:

            continue

        seen.add(
            value
        )

        deduplicated.append(
            value
        )

    return deduplicated


if __name__ == "__main__":

    sample = [

        "Memory",

        "Research",

        "Memory",

        "Wisdom",

        "Research",

        "Patterns"

    ]

    result = deduplicate_data(
        sample
    )

    print(result)

    assert len(result) == 4

    assert result == [

        "Memory",

        "Research",

        "Wisdom",

        "Patterns"

    ]

