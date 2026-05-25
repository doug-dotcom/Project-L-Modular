import os

from openai import OpenAI

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

try:
    from tavily import TavilyClient
    TAVILY_PACKAGE_AVAILABLE = True
except Exception as e:
    print("BRITTANY IMPORT ERROR:", e)
    TavilyClient = None
    TAVILY_PACKAGE_AVAILABLE = False

OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-4o-mini"
)

TAVILY_API_KEY = os.getenv(
    "TAVILY_API_KEY",
    ""
)

client = OpenAI() if os.getenv("OPENAI_API_KEY") else None

if TAVILY_PACKAGE_AVAILABLE and TAVILY_API_KEY:

    tavily = TavilyClient(
        api_key=TAVILY_API_KEY
    )

else:

    tavily = None

BRITTANY_SYSTEM = """
You are Brittany Browser.

You are Project L's web investigation specialist.

- Stay factual.
- Separate evidence from assumptions.
- Never fake web results.
- ADHD friendly formatting.
"""

def should_handle(message: str) -> bool:

    text = (message or "").lower()

    triggers = [

        "research",
        "search the web",
        "look up",
        "investigate",
        "browser",
        "brittany",
        "latest",
        "current",
        "news",
        "compare",
        "source",
        "evidence"

    ]

    return any(
        t in text
        for t in triggers
    )

def browser_research(query: str):

    if not TAVILY_PACKAGE_AVAILABLE:

        return {

            "ok": False,
            "error": "Tavily package missing.",
            "results": []

        }

    if not TAVILY_API_KEY:

        return {

            "ok": False,
            "error": "Missing TAVILY_API_KEY.",
            "results": []

        }

    if tavily is None:

        return {

            "ok": False,
            "error": "Tavily client not initialized.",
            "results": []

        }

    try:

        results = tavily.search(

            query=query,

            search_depth="advanced",

            max_results=5,

            include_answer=True

        )

        clean = []

        for r in results.get("results", []):

            clean.append({

                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", "")

            })

        return {

            "ok": True,
            "answer": results.get("answer", ""),
            "results": clean

        }

    except Exception as e:

        return {

            "ok": False,
            "error": str(e),
            "results": []

        }

def format_findings(data):

    if not data.get("ok"):

        return (
            "LIVE SEARCH FAILED:\n"
            + data.get("error", "Unknown error")
        )

    output = ""

    if data.get("answer"):

        output += "SUMMARY:\n"
        output += data.get("answer", "")
        output += "\n\n"

    for idx, item in enumerate(data.get("results", [])):

        output += f"\nSOURCE {idx+1}\n"

        output += (
            "TITLE: "
            + item.get("title", "")
            + "\n"
        )

        output += (
            "URL: "
            + item.get("url", "")
            + "\n"
        )

        output += (
            "CONTENT:\n"
            + item.get("content", "")
            + "\n\n"
        )

    return output

def investigate(message: str):

    search_data = browser_research(message)

    findings = format_findings(search_data)

    if not client:

        return findings

    response = client.chat.completions.create(

        model=OPENAI_MODEL,

        messages=[

            {
                "role": "system",
                "content": BRITTANY_SYSTEM
            },

            {
                "role": "user",
                "content":
                    "QUESTION:\n\n"
                    + message
                    + "\n\nWEB RESULTS:\n\n"
                    + findings
            }

        ],

        temperature=0.4

    )

    return (
        response
        .choices[0]
        .message
        .content
    )
