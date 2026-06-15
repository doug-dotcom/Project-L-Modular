# =====================================================
# FRANK
# RAT PACK - RESEARCH ANALYSIS TEAM
# AODS 1
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
        "agent": "Frank",
        "status": "fallback",
        "summary": "",
        "key_findings": [],
        "entities": [],
        "confidence": "LOW",
        "lessons": [
            reason
        ]
    }


# =====================================================
# SOURCE PACKET
# =====================================================

def _build_source_packet(results: dict) -> str:
    packet = ""

    for idx, result in enumerate(results.get("results", [])):
        title = result.get("title", "")
        url = result.get("url", "")
        content = str(result.get("content", "") or "")

        packet += f"""
SOURCE {idx + 1}

TITLE:
{title}

URL:
{url}

CONTENT:
{content[:1500]}
"""

    return packet.strip()


# =====================================================
# FRANK ANALYSIS
# =====================================================

def run_frank(
    query: str,
    results: dict
):
    """
    Frank turns search results into structured research analysis.
    Input:
        query: search query used
        results: Tavily-style results dict
    Output:
        dict with summary, findings, entities, confidence, lessons
    """

    if not client:
        return _fallback("OpenAI unavailable")

    source_packet = _build_source_packet(results)

    if not source_packet:
        return _fallback("No source material supplied")

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
You are Frank.

You are the lead analyst for the RAT Pack:
Research Analysis Team.

Your job is to turn supplied search results into a clear research analysis.

Return valid JSON only.

Required JSON format:

{
    "agent": "Frank",
    "status": "ok",
    "summary": "",
    "key_findings": [],
    "entities": [],
    "confidence": "",
    "lessons": []
}

Rules:
- Use only the supplied source material.
- Do not invent facts.
- Keep findings concise.
- Extract important people, organisations, laws, concepts, products, and dates.
- Confidence must be HIGH, MEDIUM, or LOW.
- Lessons should explain what Doug or Project L should take from the research.
"""
                },
                {
                    "role": "user",
                    "content": f"""
QUERY:
{query}

SOURCE MATERIAL:
{source_packet}
"""
                }
            ],
            temperature=0.2
        )

        content = response.choices[0].message.content.strip()

        data = json.loads(content)

        data.setdefault("agent", "Frank")
        data.setdefault("status", "ok")
        data.setdefault("summary", "")
        data.setdefault("key_findings", [])
        data.setdefault("entities", [])
        data.setdefault("confidence", "LOW")
        data.setdefault("lessons", [])

        return data

    except Exception as e:
        return _fallback(f"Frank analysis failed: {str(e)}")


# =====================================================
# DIRECT TEST
# =====================================================

if __name__ == "__main__":
    test_results = {
        "results": [
            {
                "title": "Test Source",
                "url": "https://example.com",
                "content": "This is a test source about research, evidence, and analysis."
            }
        ]
    }

    result = run_frank(
        "test research query",
        test_results
    )

    print(json.dumps(result, indent=2))
