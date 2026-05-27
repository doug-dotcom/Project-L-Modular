from dotenv import load_dotenv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

load_dotenv(ROOT / ".env")

import os

from tavily import TavilyClient

TAVILY_API_KEY = os.getenv(
    "TAVILY_API_KEY",
    ""
)

tavily = TavilyClient(
    api_key=TAVILY_API_KEY
)

def should_handle(message: str) -> bool:

    text = (message or "").lower()

    triggers = [

        "research",
        "latest",
        "news",
        "search",
        "web",
        "browser",
        "brittany"

    ]

    return any(
        t in text
        for t in triggers
    )

def investigate(message: str):

    try:

        results = tavily.search(

            query=message,

            search_depth="advanced",

            max_results=5

        )

        output = "# 🌐 Brittany Browser\n\n"

        for idx, r in enumerate(
            results.get("results", [])
        ):

            output += (
                f"## Source {idx+1}\n\n"
            )

            output += (
                r.get("title", "")
                + "\n\n"
            )

            output += (
                r.get("url", "")
                + "\n\n"
            )

            output += (
                r.get("content", "")
                + "\n\n"
            )

        return output

    except Exception as e:

        return f"""

# 🌐 Brittany Error

{str(e)}

Check:
- TAVILY_API_KEY
- internet connection

"""


