# =====================================================
# FRANK -> RONNIE BRIDGE
# RAT PACK
# AODS 8
# =====================================================

from agents.ronnie.ronnie import (
    run_ronnie_reflector
)


# =====================================================
# BUILD EXPERIENCE
# =====================================================

def _build_experience(
    frank_output,
    rannie_output=None
):

    sections = []

    summary = (
        frank_output.get(
            "summary",
            ""
        )
    )

    if summary:

        sections.append(
            f"SUMMARY:\n{summary}"
        )

    findings = (
        frank_output.get(
            "key_findings",
            []
        )
        or
        []
    )

    if findings:

        sections.append(
            "KEY FINDINGS:\n"
            +
            "\n".join(
                f"- {x}"
                for x in findings
            )
        )

    if rannie_output:

        relationships = (
            rannie_output.get(
                "relationships",
                []
            )
            or
            []
        )

        if relationships:

            sections.append(
                "RELATIONSHIPS:\n"
                +
                "\n".join(
                    f"- {x}"
                    for x in relationships
                )
            )

    return "\n\n".join(
        sections
    )


# =====================================================
# BRIDGE
# =====================================================

def run_frank_ronnie_bridge(
    frank_output,
    rannie_output=None
):

    experience = (
        _build_experience(
            frank_output,
            rannie_output
        )
    )

    ronnie_result = (
        run_ronnie_reflector(
            experience
        )
    )

    return {

        "agent":
            "Frank Ronnie Bridge",

        "experience":
            experience,

        "ronnie_result":
            ronnie_result

    }


# =====================================================
# TEST
# =====================================================

if __name__ == "__main__":

    sample_frank = {

        "summary":
            "Exercise, sleep and social connection repeatedly appear in dementia prevention research.",

        "key_findings": [

            "Exercise appears repeatedly",

            "Sleep quality appears repeatedly",

            "Social connection appears repeatedly"

        ]

    }

    result = (
        run_frank_ronnie_bridge(
            sample_frank
        )
    )

    import json

    print(
        json.dumps(
            result,
            indent=2
        )
    )
