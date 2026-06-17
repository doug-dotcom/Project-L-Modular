# =====================================================
# RELATIONSHIP COUNTER
# TIER 1 - AODS 3
# =====================================================

from collections import Counter
from typing import List, Dict, Any


def count_relationships(
    relationships: List[Any]
) -> Dict[str, int]:

    counter = Counter()

    for item in relationships or []:

        if isinstance(item, dict):

            value = item.get(
                "relationship",
                ""
            )

        else:

            value = str(item)

        value = value.strip().lower()

        if value:

            counter[value] += 1

    return dict(
        counter.most_common()
    )


if __name__ == "__main__":

    sample = [

        {"relationship": "supports"},
        {"relationship": "supports"},
        {"relationship": "teaches"},
        {"relationship": "supports"},
        {"relationship": "guides"}

    ]

    result = count_relationships(
        sample
    )

    print(result)

    assert result["supports"] == 3
    assert result["teaches"] == 1
    assert result["guides"] == 1

