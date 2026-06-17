# =====================================================
# TRAINING DATASET
# TIER 3 - AODS 6
# =====================================================

from typing import Dict


def build_training_dataset(
    research_corpus: Dict,
    theme_corpus: Dict,
    lesson_corpus: Dict,
    wisdom_corpus: Dict,
    relationship_corpus: Dict
) -> Dict:

    return {

        "agent":
            "Training Dataset",

        "research":
            research_corpus,

        "themes":
            theme_corpus,

        "lessons":
            lesson_corpus,

        "wisdom":
            wisdom_corpus,

        "relationships":
            relationship_corpus

    }


if __name__ == "__main__":

    result = build_training_dataset(

        research_corpus = {

            "record_count": 10

        },

        theme_corpus = {

            "theme_count": 5

        },

        lesson_corpus = {

            "lesson_count": 3

        },

        wisdom_corpus = {

            "wisdom_count": 2

        },

        relationship_corpus = {

            "relationship_count": 4

        }

    )

    print(result)

    assert result["research"]["record_count"] == 10

    assert result["themes"]["theme_count"] == 5

    assert result["wisdom"]["wisdom_count"] == 2

