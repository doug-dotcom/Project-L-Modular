import os

from pathlib import Path

from dotenv import load_dotenv

from openai import OpenAI

from tavily import TavilyClient

# =====================================================
# ROOT
# =====================================================

ROOT = Path(__file__).resolve().parents[2]

load_dotenv(ROOT / ".env")

# =====================================================
# ENV
# =====================================================

TAVILY_API_KEY = os.getenv(
    "TAVILY_API_KEY",
    ""
)

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY",
    ""
)

OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-4o-mini"
)

# =====================================================
# CLIENTS
# =====================================================

tavily = TavilyClient(
    api_key=TAVILY_API_KEY
)

client = OpenAI(
    api_key=OPENAI_API_KEY
)

# =====================================================
# SAFE TRIGGERS
# =====================================================

def should_handle(message: str) -> bool:

    text = (message or "").lower()

    triggers = [

        "research online",
        "search online",
        "browser",
        "brittany",
        "find online",
        "check online",
        "latest news",
        "current information"

    ]

    return any(
        t in text
        for t in triggers
    )

# =====================================================
# QUERY PLANNER
# =====================================================

def build_search_query(
    message: str
) -> str:

    raw = (message or "").strip()

    if not raw:
        return ""

    try:

        response = (
            client.chat.completions.create(

                model=OPENAI_MODEL,

                temperature=0.1,

                messages=[

                    {
                        "role": "system",

                        "content": """

You are Brittany's query planner.

Convert the user's request into:
- one concise
- high relevance
- internet search query

RULES:
- remove conversational filler
- preserve names/dates/places
- preserve important medical/legal/technical context
- do NOT answer the question
- output ONLY the query
- max 300 chars

"""
                    },

                    {
                        "role": "user",
                        "content": raw
                    }

                ]

            )
        )

        return (
            response
            .choices[0]
            .message
            .content
            .strip()[:300]
        )

    except Exception:

        return raw[:300]

# =====================================================
# RELEVANCE FILTER
# =====================================================

def score_result(
    original_message: str,
    result_content: str
):

    try:

        response = (
            client.chat.completions.create(

                model=OPENAI_MODEL,

                temperature=0,

                messages=[

                    {
                        "role": "system",

                        "content": """

You are Brittany's relevance scorer.

Score relevance from 0.0 to 1.0

Only score HIGH if:
- directly relevant
- contextually aligned
- useful to the user

Score LOW if:
- semantic collision
- weak relation
- generic information
- unrelated academic content

Return ONLY a number.

"""
                    },

                    {
                        "role": "user",

                        "content":
                            f"""

USER MESSAGE:
{original_message}

SEARCH RESULT:
{result_content}

"""
                    }

                ]

            )
        )

        score = (
            response
            .choices[0]
            .message
            .content
            .strip()
        )

        return float(score)

    except Exception:

        return 0.5

# =====================================================
# AI OVERVIEW SYNTHESIS
# =====================================================

def build_overview(
    original_message: str,
    filtered_results
):

    joined = "\n\n".join(filtered_results)

    try:

        response = (
            client.chat.completions.create(

                model=OPENAI_MODEL,

                temperature=0.2,

                messages=[

                    {
                        "role": "system",

                        "content": """

You are Brittany Browser v2.

Your job:
- synthesize research
- reduce noise
- extract meaning
- produce concise AI overview output

DO:
- summarize key findings
- identify consensus themes
- explain relevance clearly

DO NOT:
- dump raw search content
- spam sources
- include irrelevant detail

FORMAT:

# 🌐 Brittany Browser

## AI Overview
(summary)

## Key Findings
- bullet points

## Relevant Sources
- concise source references

"""
                    },

                    {
                        "role": "user",

                        "content":
                            f"""

USER MESSAGE:
{original_message}

FILTERED RESULTS:
{joined}

"""
                    }

                ]

            )
        )

        return (
            response
            .choices[0]
            .message
            .content
        )

    except Exception as e:

        return f"Brittany synthesis error: {str(e)}"

# =====================================================
# MAIN INVESTIGATION
# =====================================================

def investigate(message: str):

    try:

        query = build_search_query(message)

        results = tavily.search(

            query=query,

            search_depth="advanced",

            max_results=8

        )

        filtered = []

        for r in results.get("results", []):

            content = (
                r.get("title", "")
                + "\n\n"
                + r.get("content", "")
            )

            relevance = score_result(
                message,
                content
            )

            if relevance >= 0.72:

                filtered.append(

                    f"""

TITLE:
{r.get("title", "")}

URL:
{r.get("url", "")}

CONTENT:
{r.get("content", "")}

"""

                )

        if not filtered:

            return """

# 🌐 Brittany Browser

## AI Overview

No highly relevant external information found.

"""

        return build_overview(
            message,
            filtered
        )

    except Exception as e:

        return f"""

# 🌐 Brittany Error

{str(e)}

"""
