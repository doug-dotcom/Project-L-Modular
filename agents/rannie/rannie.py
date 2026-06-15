# =====================================================
# RANNIE
# RESEARCH RELATIONSHIP MAPPER
# AODS 7
# =====================================================

import os
import json

from openai import OpenAI


# =====================================================
# OPENAI
# =====================================================

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY",
    ""
)

OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-4o-mini"
)

client = OpenAI(
    api_key=OPENAI_API_KEY
) if OPENAI_API_KEY else None


# =====================================================
# FALLBACK
# =====================================================

def _fallback(reason):

    return {

        "agent":
            "Rannie",

        "status":
            "fallback",

        "relationships":
            [],

        "themes":
            [],

        "notes":
            [reason]
    }


# =====================================================
# PACKET BUILDER
# =====================================================

def _build_packet(dot_output):

    packet = ""

    for fact in dot_output.get(
        "facts",
        []
    ):

        packet += f"\nFACT:\n{fact}\n"

    for study in dot_output.get(
        "studies",
        []
    ):

        packet += f"\nSTUDY:\n{study}\n"

    return packet


# =====================================================
# RANNIE
# =====================================================

def run_rannie(dot_output):

    if not client:

        return _fallback(
            "OpenAI unavailable"
        )

    packet = _build_packet(
        dot_output
    )

    if not packet:

        return _fallback(
            "No facts supplied"
        )

    try:

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            response_format={
                "type": "json_object"
            },
            messages=[
                {
                    "role": "system",
                    "content": """
You are Rannie.

You are the Research Relationship Mapper.

Your job is to identify:

- Relationships
- Connections
- Cause and effect
- Themes
- Recurring patterns

Return valid JSON only.

{
    "agent": "Rannie",
    "status": "ok",
    "relationships": [],
    "themes": [],
    "notes": []
}
"""
                },
                {
                    "role": "user",
                    "content": packet
                }
            ],
            temperature=0.2
        )

        data = json.loads(
            response.choices[0].message.content
        )

        data.setdefault(
            "agent",
            "Rannie"
        )

        data.setdefault(
            "status",
            "ok"
        )

        data.setdefault(
            "relationships",
            []
        )

        data.setdefault(
            "themes",
            []
        )

        data.setdefault(
            "notes",
            []
        )

        return data

    except Exception as e:

        return _fallback(
            f"Relationship mapping failed: {str(e)}"
        )


# =====================================================
# TEST
# =====================================================

if __name__ == "__main__":

    sample = {

        "facts": [

            "Exercise improves cardiovascular health",

            "Cardiovascular health is linked to dementia risk",

            "Sleep quality affects brain recovery"

        ]

    }

    result = run_rannie(
        sample
    )

    print(
        json.dumps(
            result,
            indent=2
        )
    )
