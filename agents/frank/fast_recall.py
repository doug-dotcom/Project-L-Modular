# =====================================================
# FAST RECALL
# TIER 1 - AODS 10
# =====================================================

from typing import List, Dict, Any


def fast_recall(
    records: List[Dict[str, Any]],
    limit: int = 5
) -> List[Dict[str, Any]]:

    if not records:
        return []

    sorted_records = sorted(

        records,

        key=lambda x: x.get(
            "importance",
            0
        ),

        reverse=True

    )

    return sorted_records[:limit]


if __name__ == "__main__":

    records = [

        {
            "id": 1,
            "importance": 50
        },

        {
            "id": 2,
            "importance": 90
        },

        {
            "id": 3,
            "importance": 75
        }

    ]

    result = fast_recall(
        records,
        limit=2
    )

    print(result)

    assert len(result) == 2

    assert result[0]["id"] == 2

    assert result[1]["id"] == 3

