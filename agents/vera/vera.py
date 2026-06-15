# =====================================================
# VERA
# RAT PACK - SOURCE VERIFIER
# AODS 4
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
        "agent": "Vera",
        "status": "fallback",
        "overall_confidence": "LOW",
        "verified_sources": [],
        "notes": [
            reason
        ]
    }


# =====================================================
# VERA SOURCE VERIFIER
# =====================================================

def run_vera(sources):
    """
    Vera evaluates source quality and credibility.

    Input:
        sources = Scout output list

    Output:
        credibility assessment
    """

    if not client:
        return _fallback("OpenAI unavailable")

    if not sources:
        return _fallback("No sources supplied")

    try:

        source_packet = ""

        for idx, source in enumerate(sources):

            source_packet += f"""

SOURCE {idx + 1}

TITLE:
{source.get('title', '')}

URL:
{source.get('url', '')}

CONTENT:
{source.get('content', '')[:1000]}
"""

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            response_format={
                "type": "json_object"
            },
            messages=[
                {
                    "role": "system",
                    "content": """
You are Vera.

You are the RAT Pack Source Verification Specialist.

Evaluate credibility and trustworthiness.

Return valid JSON only.

{
    "agent": "Vera",
    "status": "ok",
    "overall_confidence": "",
    "verified_sources": [],
    "notes": []
}

Confidence:
HIGH
MEDIUM
LOW

Evaluate:

Government
Academic
Medical
Industry
News
Blog
Forum

Do not invent facts.
"""
                },
                {
                    "role": "user",
                    "content": source_packet
                }
            ],
            temperature=0.1
        )

        data = json.loads(
            response.choices[0].message.content
        )

        data.setdefault(
            "agent",
            "Vera"
        )

        data.setdefault(
            "status",
            "ok"
        )

        data.setdefault(
            "overall_confidence",
            "LOW"
        )

        data.setdefault(
            "verified_sources",
            []
        )

        data.setdefault(
            "notes",
            []
        )

        return data

    except Exception as e:

        return _fallback(
            f"Verification failed: {str(e)}"
        )


# =====================================================
# DIRECT TEST
# =====================================================

if __name__ == "__main__":

    sample_sources = [
        {
            "title": "NIH Study",
            "url": "https://nih.gov",
            "content": "Example content"
        }
    ]

    result = run_vera(
        sample_sources
    )

    print(
        json.dumps(
            result,
            indent=2
        )
    )
