import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI()

# =====================================================
# TAVILY IMPORT
# =====================================================

try:
    from tavily import TavilyClient
    TAVILY_PACKAGE_AVAILABLE = True
except Exception as e:
    print("BRITTANY TAVILY IMPORT ERROR:", e)
    TavilyClient = None
    TAVILY_PACKAGE_AVAILABLE = False


TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

if TAVILY_PACKAGE_AVAILABLE and TAVILY_API_KEY:
    tavily = TavilyClient(api_key=TAVILY_API_KEY)
else:
    tavily = None


BRITTANY_SYSTEM = """
You are Brittany Browser.

You are Shine L's specialist web investigator.

Rules:
- Do not pretend live browsing worked if retrieval failed.
- Separate verified findings from assumptions.
- Explain uncertainty honestly.
- Stay structured, calm, and evidence-aware.
- ADHD friendly formatting.
"""


def should_handle(message: str) -> bool:
    text = message.lower()

    triggers = [
        "research",
        "search the web",
        "look up",
        "investigate",
        "find sources",
        "web search",
        "browser",
        "brittany",
        "verify online",
        "latest",
        "current",
        "source",
        "evidence",
        "news",
        "compare",
        "valuation"
    ]

    return any(t in text for t in triggers)


def browser_research(query: str):

    if not TAVILY_PACKAGE_AVAILABLE:
        return {
            "ok": False,
            "error": "Tavily package is not installed or failed to import.",
            "results": []
        }

    if not TAVILY_API_KEY:
        return {
            "ok": False,
            "error": "TAVILY_API_KEY is missing from environment.",
            "results": []
        }

    if tavily is None:
        return {
            "ok": False,
            "error": "Tavily client was not created.",
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

        for result in results.get("results", []):
            clean.append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "content": result.get("content", "")
            })

        return {
            "ok": True,
            "answer": results.get("answer", ""),
            "results": clean
        }

    except Exception as e:
        print("BRITTANY SEARCH ERROR:", e)

        return {
            "ok": False,
            "error": str(e),
            "results": []
        }


def format_findings(search_data):

    if not search_data.get("ok"):
        return (
            "LIVE SEARCH FAILED:\n"
            + search_data.get("error", "Unknown error")
        )

    output = ""

    if search_data.get("answer"):
        output += "TAVILY ANSWER:\n"
        output += search_data.get("answer", "")
        output += "\n\n"

    results = search_data.get("results", [])

    if not results:
        return "No live web results returned."

    for idx, item in enumerate(results):
        output += f"\nSOURCE {idx+1}\n"
        output += "TITLE: " + item.get("title", "") + "\n"
        output += "URL: " + item.get("url", "") + "\n"
        output += "CONTENT:\n" + item.get("content", "") + "\n\n"

    return output


def investigate(message: str) -> str:

    search_data = browser_research(message)

    formatted_findings = format_findings(search_data)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": BRITTANY_SYSTEM
            },
            {
                "role": "user",
                "content":
                    "Research Question:\n\n"
                    + message
                    + "\n\nLIVE WEB FINDINGS:\n\n"
                    + formatted_findings
            }
        ]
    )

    final = response.choices[0].message.content

    if not search_data.get("ok"):
        final += (
            "\n\nBrittany Diagnostic:\n"
            + search_data.get("error", "Unknown Tavily error")
        )

    return final
