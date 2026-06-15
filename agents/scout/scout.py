# =====================================================
# SCOUT
# RAT PACK - SOURCE FINDER
# AODS 3
# =====================================================

import os
import json

from pathlib import Path
from dotenv import load_dotenv

from tavily import TavilyClient

ROOT = Path(__file__).resolve().parents[2]

load_dotenv(ROOT / ".env")


# =====================================================
# TAVILY
# =====================================================

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

tavily = TavilyClient(api_key=TAVILY_API_KEY) if TAVILY_API_KEY else None


# =====================================================
# LIMITS
# =====================================================

MAX_RESULTS_PER_QUERY = 5
MAX_CONTENT_CHARS = 2000


# =====================================================
# FALLBACK
# =====================================================

def _fallback(reason: str):
    return {
        "agent": "Scout",
        "status": "fallback",
        "source_count": 0,
        "sources": [],
        "notes": [
            reason
        ]
    }


# =====================================================
# SOURCE NORMALISER
# =====================================================

def _normalise_source(query: str, result: dict):
    content = str(result.get("content", "") or "")

    if len(content) > MAX_CONTENT_CHARS:
        content = content[:MAX_CONTENT_CHARS] + "\n\n[SCOUT CONTENT TRIMMED]"

    return {
        "query": query,
        "title": result.get("title", ""),
        "url": result.get("url", ""),
        "content": content,
        "score": result.get("score", None)
    }


# =====================================================
# SCOUT SOURCE FINDER
# =====================================================

def run_scout(search_queries):
    """
    Scout searches the web for one or more search queries
    and returns a clean source catalogue.

    Input:
        search_queries: list[str] or str

    Output:
        dict with sources
    """

    if not tavily:
        return _fallback("Tavily unavailable")

    if isinstance(search_queries, str):
        queries = [
            search_queries
        ]
    else:
        queries = list(search_queries or [])

    queries = [
        str(q).strip()
        for q in queries
        if str(q).strip()
    ]

    if not queries:
        return _fallback("No search queries supplied")

    all_sources = []
    seen_urls = set()
    notes = []

    for query in queries:
        try:
            results = tavily.search(
                query=query,
                search_depth="advanced",
                max_results=MAX_RESULTS_PER_QUERY
            )

            for result in results.get("results", []):
                url = result.get("url", "")

                if not url:
                    continue

                if url in seen_urls:
                    continue

                seen_urls.add(url)

                all_sources.append(
                    _normalise_source(
                        query,
                        result
                    )
                )

        except Exception as e:
            notes.append(
                f"Search failed for query '{query}': {str(e)}"
            )

    return {
        "agent": "Scout",
        "status": "ok",
        "source_count": len(all_sources),
        "sources": all_sources,
        "notes": notes
    }


# =====================================================
# DIRECT TEST
# =====================================================

if __name__ == "__main__":
    result = run_scout(
        [
            "dementia prevention strongest evidence",
            "exercise sleep social connection dementia prevention"
        ]
    )

    print(json.dumps(result, indent=2))

