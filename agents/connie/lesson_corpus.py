# =====================================================
# LESSON CORPUS
# TIER 3 - AODS 3
# =====================================================

from collections import Counter
from typing import List, Dict


def build_lesson_corpus(
    lessons: List[str]
) -> Dict:

    counter = Counter()

    for lesson in lessons or []:

        clean = str(
            lesson
        ).strip()

        if clean:

            counter[clean] += 1

    return {

        "agent":
            "Lesson Corpus",

        "lesson_count":
            len(counter),

        "lessons":
            dict(
                counter.most_common()
            )

    }


if __name__ == "__main__":

    sample = [

        "Store before recall",

        "Store before recall",

        "Patterns create knowledge",

        "Knowledge creates wisdom",

        "Store before recall"

    ]

    result = build_lesson_corpus(
        sample
    )

    print(result)

    assert result["lesson_count"] == 3

    assert result["lessons"]["Store before recall"] == 3

