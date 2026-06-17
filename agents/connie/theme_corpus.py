# =====================================================
# THEME CORPUS
# TIER 3 - AODS 2
# =====================================================

from collections import Counter
from typing import List, Dict


def build_theme_corpus(
    themes: List[str]
) -> Dict:

    counter = Counter()

    for theme in themes or []:

        clean = str(
            theme
        ).strip().lower()

        if clean:

            counter[clean] += 1

    return {

        "agent":
            "Theme Corpus",

        "theme_count":
            len(counter),

        "themes":
            dict(
                counter.most_common()
            )

    }


if __name__ == "__main__":

    sample = [

        "memory",
        "research",
        "memory",
        "wisdom",
        "memory",
        "research"

    ]

    result = build_theme_corpus(
        sample
    )

    print(result)

    assert result["theme_count"] == 3

    assert result["themes"]["memory"] == 3

