# =====================================================
# MODEL EVALUATION
# TIER 5 - AODS 5
# =====================================================

from typing import Dict


def evaluate_model(
    test_cases: int,
    passed_cases: int
) -> Dict:

    if test_cases <= 0:

        accuracy = 0

    else:

        accuracy = round(

            (passed_cases / test_cases) * 100,

            2

        )

    return {

        "agent":
            "Model Evaluation",

        "test_cases":
            test_cases,

        "passed_cases":
            passed_cases,

        "accuracy":
            accuracy,

        "status":

            "pass"

            if accuracy >= 80

            else

            "fail"

    }


if __name__ == "__main__":

    result = evaluate_model(

        test_cases = 100,

        passed_cases = 92

    )

    print(result)

    assert result["accuracy"] == 92.0

    assert result["status"] == "pass"

