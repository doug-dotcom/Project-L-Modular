# =====================================================
# MISSING KNOWLEDGE DETECTOR
# TIER 1 - AODS 5
# =====================================================

from typing import List


def detect_missing_knowledge(
    required_knowledge: List[str],
    available_knowledge: List[str]
) -> List[str]:

    required = {

        str(x).strip().lower()

        for x in required_knowledge
    }

    available = {

        str(x).strip().lower()

        for x in available_knowledge
    }

    missing = required - available

    return sorted(
        list(missing)
    )


if __name__ == "__main__":

    required = [

        "memory",
        "patterns",
        "knowledge",
        "wisdom",
        "intuition"

    ]

    available = [

        "memory",
        "patterns",
        "knowledge"

    ]

    result = detect_missing_knowledge(
        required,
        available
    )

    print(result)

    assert "wisdom" in result
    assert "intuition" in result
    assert len(result) == 2

