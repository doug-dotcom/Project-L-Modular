# =====================================================
# LORA PREPARATION
# TIER 5 - AODS 3
# =====================================================

from typing import Dict, List


def prepare_lora_dataset(
    corpus: List[Dict]
) -> Dict:

    training_examples = []

    for item in corpus or []:

        question = item.get(
            "question",
            ""
        )

        summary = item.get(
            "summary",
            ""
        )

        training_examples.append({

            "instruction":
                question,

            "response":
                summary

        })

    return {

        "agent":
            "LoRA Preparation",

        "training_example_count":
            len(training_examples),

        "training_examples":
            training_examples

    }


if __name__ == "__main__":

    sample = [

        {

            "question":
                "How does exercise affect cognition?",

            "summary":
                "Exercise improves cognition"

        },

        {

            "question":
                "How does sleep affect memory?",

            "summary":
                "Sleep improves memory"

        }

    ]

    result = prepare_lora_dataset(
        sample
    )

    print(result)

    assert result["training_example_count"] == 2

    assert result["training_examples"][0]["instruction"] == \
        "How does exercise affect cognition?"

