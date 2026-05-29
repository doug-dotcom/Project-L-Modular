import os
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from tavily import TavilyClient

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

tavily = TavilyClient(api_key=TAVILY_API_KEY)
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

MAX_BRITTANY_CONTENT_CHARS = 2000
MAX_BRITTANY_OUTPUT_CHARS = 12000


def should_handle(message: str) -> bool:

    text = (message or "").lower()

    triggers = [
        "research online",
        "browser",
        "brittany",
        "find online",
        "check online",
       
    ]

    return any(
        t in text
        for t in triggers
    )


def build_search_query(message: str) -> str:

    raw = (message or "").strip()

    if not raw:
        return ""

    if not client:
        return raw[:350]

    try:

        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Brittany's search query planner. "
                        "Convert the user's request into one concise, targeted web search query. "
                        "Remove conversational filler. "
                        "Keep names, dates, companies, locations, and key facts. "
                        "Do not answer the question. "
                        "Return only the search query. "
                        "Maximum 300 characters."
                    )
                },
                {
                    "role": "user",
                    "content": raw
                }
            ],
            temperature=0.1
        )

        query = response.choices[0].message.content.strip()

        if not query:
            query = raw

        return query[:350]

    except Exception:

        return raw[:350]


def investigate(message: str):

    try:

        query = build_search_query(message)

        results = tavily.search(
            query=query,
            search_depth="advanced",
            max_results=5
        )

        output = "# 🌐 Brittany Browser\n\n"
        output += f"Search query used:\n{query}\n\n"

        for idx, r in enumerate(
            results.get("results", [])
        ):

            output += f"## Source {idx+1}\n\n"

            output += (
                r.get("title", "")
                + "\n\n"
            )

            output += (
                r.get("url", "")
                + "\n\n"
            )

            content = str(
                r.get("content", "")
                or ""
            )

            if len(content) > MAX_BRITTANY_CONTENT_CHARS:
                content = (
                    content[:MAX_BRITTANY_CONTENT_CHARS]
                    + "\n\n[BRITTANY CONTENT TRIMMED]"
                )

            output += content + "\n\n"

        if len(output) > MAX_BRITTANY_OUTPUT_CHARS:
            output = (
                output[:MAX_BRITTANY_OUTPUT_CHARS]
                + "\n\n[BRITTANY OUTPUT TRIMMED]"
            )

        return output

    except Exception as e:

        return f"""
# 🌐 Brittany Error

{str(e)}

Check:
- TAVILY_API_KEY
- OPENAI_API_KEY
- internet connection
- query length
"""

