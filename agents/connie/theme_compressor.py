# =====================================================
# THEME COMPRESSOR
# TIER 2 - AODS 9
# =====================================================

from collections import Counter
from typing import List, Dict


def compress_themes(
    themes: List[str],
    top_n: int = 5
) -> Dict:

    counter = Counter()

    for theme in themes or []:

        clean = str(
            theme
        ).strip().lower()

        if clean:

            counter[clean] += 1

    compressed = dict(
        counter.most_common(top_n)
    )

    return {

        "agent":
            "Theme Compressor",

        "theme_count":
            len(counter),

        "compressed_count":
            len(compressed),

        "themes":
            compressed

    }


if __name__ == "__main__":

    sample = [

        "memory",
        "research",
        "memory",
        "patterns",
        "memory",
        "wisdom",
        "research"

    ]

    result = compress_themes(
        sample
    )

    print(result)

    assert result["themes"]["memory"] == 3

    assert result["themes"]["research"] == 2

