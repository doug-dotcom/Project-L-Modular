# =====================================================
# LORA TRAINING
# TIER 5 - AODS 4
# =====================================================

from typing import Dict


def run_lora_training(
    training_example_count: int,
    epochs: int = 3
) -> Dict:

    estimated_steps = (
        training_example_count * epochs
    )

    return {

        "agent":
            "LoRA Training",

        "training_example_count":
            training_example_count,

        "epochs":
            epochs,

        "estimated_steps":
            estimated_steps,

        "status":
            "ready_for_training"

    }


if __name__ == "__main__":

    result = run_lora_training(

        training_example_count = 100,

        epochs = 3

    )

    print(result)

    assert result["estimated_steps"] == 300

    assert result["status"] == \
        "ready_for_training"

