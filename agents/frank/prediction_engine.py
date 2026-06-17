# =====================================================
# PREDICTION ENGINE
# TIER 2 - AODS 7
# =====================================================

from typing import Dict


def generate_prediction(
    forecast: Dict
) -> Dict:

    predictions = []

    for pattern, data in forecast.items():

        current = data.get(
            "current_count",
            0
        )

        projected = data.get(
            "projected_count",
            0
        )

        trend = (

            "increasing"

            if projected > current

            else

            "stable"

        )

        predictions.append({

            "pattern":
                pattern,

            "current":
                current,

            "projected":
                projected,

            "trend":
                trend

        })

    return {

        "agent":
            "Prediction Engine",

        "prediction_count":
            len(predictions),

        "predictions":
            predictions

    }


if __name__ == "__main__":

    sample = {

        "memory": {

            "current_count": 10,

            "projected_count": 12

        },

        "research": {

            "current_count": 5,

            "projected_count": 6

        }

    }

    result = generate_prediction(
        sample
    )

    print(result)

    assert result["prediction_count"] == 2

    assert result["predictions"][0]["trend"] == "increasing"

