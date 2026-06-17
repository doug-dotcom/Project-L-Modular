# =====================================================
# EXECUTIVE REPORT
# TIER 4 - AODS 8
# =====================================================

from typing import Dict


def generate_executive_report(
    research_count: int,
    insight_count: int,
    prediction_count: int
) -> Dict:

    report = {

        "research_count":
            research_count,

        "insight_count":
            insight_count,

        "prediction_count":
            prediction_count

    }

    summary = (

        f"Research: {research_count} | "

        f"Insights: {insight_count} | "

        f"Predictions: {prediction_count}"

    )

    return {

        "agent":
            "Executive Report",

        "summary":
            summary,

        "report":
            report

    }


if __name__ == "__main__":

    result = generate_executive_report(

        research_count = 25,

        insight_count = 8,

        prediction_count = 4

    )

    print(result)

    assert result["report"]["research_count"] == 25

    assert result["report"]["prediction_count"] == 4

