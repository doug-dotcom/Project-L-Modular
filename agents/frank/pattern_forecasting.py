# =====================================================
# PATTERN FORECASTING
# TIER 2 - AODS 6
# =====================================================

from typing import Dict


def forecast_patterns(
    historical_patterns: Dict[str, int]
) -> Dict:

    forecast = {}

    for pattern, count in historical_patterns.items():

        forecast[pattern] = {

            "current_count":
                count,

            "projected_count":
                round(count * 1.20)

        }

    return {

        "agent":
            "Pattern Forecasting",

        "forecast":
            forecast

    }


if __name__ == "__main__":

    sample = {

        "memory": 10,

        "research": 5,

        "wisdom": 2

    }

    result = forecast_patterns(
        sample
    )

    print(result)

    assert result["forecast"]["memory"]["projected_count"] == 12

    assert result["forecast"]["research"]["projected_count"] == 6

