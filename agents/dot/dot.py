# =====================================================
# DOT
# RAT PACK - DATA EXTRACTION SPECIALIST
# AODS 5
# =====================================================

import os
import json

from openai import OpenAI


# =====================================================
# OPENAI
# =====================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None


# =====================================================
# FALLBACK
# =====================================================

def _fallback(reason: str):
    return {
        "agent": "Dot",
        "status": "fallback",
        "facts": [],
        "statistics": [],
        "dates": [],
        "people": [],
        "organisations": [],
        "studies": [],
        "notes": [
            reason
        ]
    }


# =====================================================
# SOURCE PACKET
# =====================================================

def _build_packet(sources):

    packet = ""

    for idx, source in enumerate(sources):

        packet += f"""

SOURCE {idx + 1}

TITLE:
{source.get('title', '')}

URL:
{source.get('url', '')}

CONTENT:
{source.get('content', '')[:1500]}
"""

    return packet.strip()


# =====================================================
# DOT EXTRACTION ENGINE
# =====================================================

def run_dot(sources):
    """
    Dot extracts structured facts from research sources.

    Input:
        Scout source list

    Output:
        Structured research evidence
    """

    if not client:
        return _fallback(
            "OpenAI unavailable"
        )

    if not sources:
        return _fallback(
            "No sources supplied"
        )

    try:

        packet = _build_packet(
            sources
        )

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            response_format={
                "type": "json_object"
            },
            messages=[
                {
                    "role": "system",
                    "content": """
You are Dot.

You are the RAT Pack Data Extraction Specialist.

Extract only information found in supplied sources.

Return valid JSON only.

Format:

{
    "agent": "Dot",
    "status": "ok",
    "facts": [],
    "statistics": [],
    "dates": [],
    "people": [],
    "organisations": [],
    "studies": [],
    "notes": []
}

Rules:

- Do not invent information.
- Extract factual statements.
- Extract numerical data.
- Extract dates.
- Extract studies and research references.
- Extract named people.
- Extract organisations.
"""
                },
                {
                    "role": "user",
                    "content": packet
                }
            ],
            temperature=0.1
        )

        data = json.loads(
            response.choices[0].message.content
        )

        data.setdefault(
            "agent",
            "Dot"
        )

        data.setdefault(
            "status",
            "ok"
        )

        data.setdefault(
            "facts",
            []
        )

        data.setdefault(
            "statistics",
            []
        )

        data.setdefault(
            "dates",
            []
        )

        data.setdefault(
            "people",
            []
        )

        data.setdefault(
            "organisations",
            []
        )

        data.setdefault(
            "studies",
            []
        )

        data.setdefault(
            "notes",
            []
        )

        return data

    except Exception as e:

        return _fallback(
            f"Extraction failed: {str(e)}"
        )


# =====================================================
# DIRECT TEST
# =====================================================

if __name__ == "__main__":

    sample_sources = [
        {
            "title": "Example Study",
            "url": "https://example.com",
            "content": "A 2024 study found exercise reduced dementia risk by 20 percent."
        }
    ]

    result = run_dot(
        sample_sources
    )

    print(
        json.dumps(
            result,
            indent=2
        )
    )
