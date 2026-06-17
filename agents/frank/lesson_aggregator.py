# =====================================================
# LESSON AGGREGATOR
# TIER 2 - AODS 1
# =====================================================

from collections import Counter
from typing import List, Dict


def aggregate_lessons(
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
            "Lesson Aggregator",

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

        "Store before recall"

    ]

    result = aggregate_lessons(
        sample
    )

    print(result)

    assert result["lesson_count"] == 2

    assert result["lessons"]["Store before recall"] == 3

