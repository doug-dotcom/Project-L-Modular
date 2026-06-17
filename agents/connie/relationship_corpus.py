# =====================================================
# RELATIONSHIP CORPUS
# TIER 3 - AODS 5
# =====================================================

from collections import Counter
from typing import List, Dict, Any


def build_relationship_corpus(
    relationships: List[Any]
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

    return {

        "agent":
            "Relationship Corpus",

        "relationship_count":
            len(counter),

        "relationships":
            dict(
                counter.most_common()
            )

    }


if __name__ == "__main__":

    sample = [

        {"relationship": "supports"},
        {"relationship": "supports"},
        {"relationship": "guides"},
        {"relationship": "supports"},
        {"relationship": "teaches"},
        {"relationship": "guides"}

    ]

    result = build_relationship_corpus(
        sample
    )

    print(result)

    assert result["relationship_count"] == 3

    assert result["relationships"]["supports"] == 3

    assert result["relationships"]["guides"] == 2

