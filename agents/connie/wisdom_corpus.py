# =====================================================
# WISDOM CORPUS
# TIER 3 - AODS 4
# =====================================================

from collections import Counter
from typing import List, Dict


def build_wisdom_corpus(
    wisdom_items: List[str]
) -> Dict:

    counter = Counter()

    for item in wisdom_items or []:

        clean = str(
            item
        ).strip()

        if clean:

            counter[clean] += 1

    return {

        "agent":
            "Wisdom Corpus",

        "wisdom_count":
            len(counter),

        "wisdom":
            dict(
                counter.most_common()
            )

    }


if __name__ == "__main__":

    sample = [

        "Patterns create knowledge",

        "Knowledge creates wisdom",

        "Patterns create knowledge",

        "Trust evidence over assumptions",

        "Knowledge creates wisdom"

    ]

    result = build_wisdom_corpus(
        sample
    )

    print(result)

    assert result["wisdom_count"] == 3

    assert result["wisdom"]["Patterns create knowledge"] == 2

    assert result["wisdom"]["Knowledge creates wisdom"] == 2

