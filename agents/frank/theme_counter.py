# =====================================================
# THEME COUNTER
# TIER 1 - AODS 2
# =====================================================

from collections import Counter
from typing import List, Dict


def count_themes(themes: List[str]) -> Dict[str, int]:

    counter = Counter()

    for theme in themes or []:

        clean = str(theme).strip().lower()

        if clean:
            counter[clean] += 1

    return dict(counter.most_common())


if __name__ == "__main__":

    sample = [

        "memory",
        "research",
        "memory",
        "patterns",
        "memory",
        "research"

    ]

    result = count_themes(sample)

    print(result)

    assert result["memory"] == 3
    assert result["research"] == 2

