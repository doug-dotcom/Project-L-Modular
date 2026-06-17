# =====================================================
# RELATIONSHIP COMPRESSOR
# TIER 2 - AODS 10
# =====================================================

from collections import Counter
from typing import List, Dict, Any


def compress_relationships(
    relationships: List[Any],
    top_n: int = 5
) -> Dict:

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

    compressed = dict(
        counter.most_common(top_n)
    )

    return {

        "agent":
            "Relationship Compressor",

        "relationship_count":
            len(counter),

        "compressed_count":
            len(compressed),

        "relationships":
            compressed

    }


if __name__ == "__main__":

    sample = [

        {"relationship": "supports"},
        {"relationship": "supports"},
        {"relationship": "supports"},
        {"relationship": "guides"},
        {"relationship": "teaches"},
        {"relationship": "guides"}

    ]

    result = compress_relationships(
        sample
    )

    print(result)

    assert result["relationships"]["supports"] == 3

    assert result["relationships"]["guides"] == 2

