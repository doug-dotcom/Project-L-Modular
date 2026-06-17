# =====================================================
# RESEARCH GAP DETECTOR
# TIER 1 - AODS 4
# =====================================================

from typing import List


def detect_gaps(
    expected_topics: List[str],
    researched_topics: List[str]
) -> List[str]:

    expected = {

        str(x).strip().lower()

        for x in expected_topics
    }

    researched = {

        str(x).strip().lower()

        for x in researched_topics
    }

    gaps = expected - researched

    return sorted(
        list(gaps)
    )


if __name__ == "__main__":

    expected = [

        "memory",
        "research",
        "patterns",
        "knowledge",
        "wisdom"

    ]

    researched = [

        "memory",
        "research",
        "patterns"

    ]

    result = detect_gaps(
        expected,
        researched
    )

    print(result)

    assert "knowledge" in result
    assert "wisdom" in result
    assert len(result) == 2

