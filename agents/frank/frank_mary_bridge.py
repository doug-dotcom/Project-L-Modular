# =====================================================
# FRANK -> MARY BRIDGE
# RAT PACK
# AODS 10
# =====================================================

from agents.mary.mary_v3 import (
    create_meaning_packet
)


# =====================================================
# BUILD RESEARCH CONTENT
# =====================================================

def _build_content(
    frank_output,
    finlay_output=None,
    rannie_output=None
):

    parts = []

    summary = (
        frank_output.get(
            "summary",
            ""
        )
    )

    if summary:
        parts.append(summary)

    findings = (
        frank_output.get(
            "key_findings",
            []
        )
        or
        []
    )

    parts.extend(findings)

    if finlay_output:

        lesson = (
            finlay_output.get(
                "lesson",
                ""
            )
        )

        if lesson:
            parts.append(lesson)

    if rannie_output:

        relationships = (
            rannie_output.get(
                "relationships",
                []
            )
            or
            []
        )

        parts.extend(
            str(x)
            for x in relationships
        )

    return "\n".join(parts)


# =====================================================
# BRIDGE
# =====================================================

def run_frank_mary_bridge(
    frank_output,
    finlay_output=None,
    rannie_output=None
):

    content = _build_content(
        frank_output,
        finlay_output,
        rannie_output
    )

    row = {

        "id":
            "rat_pack",

        "content":
            content

    }

    packet = (
        create_meaning_packet(
            row,
            "memory_project_l"
        )
    )

    return {

        "agent":
            "Frank Mary Bridge",

        "content":
            content,

        "mary_packet":
            packet

    }


# =====================================================
# TEST
# =====================================================

if __name__ == "__main__":

    sample_frank = {

        "summary":
            "Exercise and sleep repeatedly appeared in research.",

        "key_findings": [

            "Exercise improves cardiovascular health",

            "Sleep improves recovery"

        ]

    }

    sample_finlay = {

        "lesson":
            "Multiple reinforcing behaviours appear important."
    }

    result = (
        run_frank_mary_bridge(
            sample_frank,
            sample_finlay
        )
    )

    import json

    print(
        json.dumps(
            result,
            indent=2
        )
    )
