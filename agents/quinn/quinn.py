# =====================================================
# QUINN
# RAT PACK - QUERY PLANNER
# AODS 2
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

def _fallback(question: str, reason: str):
    clean = (question or "").strip()

    return {
        "agent": "Quinn",
        "status": "fallback",
        "primary_question": clean,
        "research_angles": [
            clean
        ] if clean else [],
        "sub_questions": [],
        "search_queries": [
            clean
        ] if clean else [],
        "coverage_plan": "",
        "notes": [
            reason
        ]
    }


# =====================================================
# QUINN QUERY PLANNER
# =====================================================

def run_quinn(question: str):
    """
    Quinn converts one research question into a research plan
    and multiple targeted search paths.
    """

    raw = (question or "").strip()

    if not raw:
        return _fallback(
            raw,
            "No question supplied"
        )

    if not client:
        return _fallback(
            raw,
            "OpenAI unavailable"
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
You are Quinn.

You are the RAT Pack query planner.

Your job is to convert one research request into a clear research plan
and multiple targeted search queries.

Return valid JSON only.

Required JSON format:

{
    "agent": "Quinn",
    "status": "ok",
    "primary_question": "",
    "research_angles": [],
    "sub_questions": [],
    "search_queries": [],
    "coverage_plan": "",
    "notes": []
}

Rules:
- Do not answer the research question.
- Create search paths that improve coverage.
- Include synonyms, related concepts, laws, people, organisations, dates, and alternate wording where useful.
- Keep search queries concise.
- Prefer 5 to 8 search queries.
- Make the coverage plan practical.
"""
                },
                {
                    "role": "user",
                    "content": raw
                }
            ],
            temperature=0.2
        )

        content = response.choices[0].message.content.strip()
        data = json.loads(content)

        data.setdefault("agent", "Quinn")
        data.setdefault("status", "ok")
        data.setdefault("primary_question", raw)
        data.setdefault("research_angles", [])
        data.setdefault("sub_questions", [])
        data.setdefault("search_queries", [raw])
        data.setdefault("coverage_plan", "")
        data.setdefault("notes", [])

        return data

    except Exception as e:
        return _fallback(
            raw,
            f"Quinn planning failed: {str(e)}"
        )


# =====================================================
# DIRECT TEST
# =====================================================

if __name__ == "__main__":
    result = run_quinn(
        "Research dementia prevention and what the strongest evidence says"
    )

    print(json.dumps(result, indent=2))
