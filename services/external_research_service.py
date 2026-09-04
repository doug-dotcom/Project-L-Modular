"""Governed external research service without a speaking agent persona."""

from __future__ import annotations

import json
import os

from openai import OpenAI
from tavily import TavilyClient


TRIGGERS = (
    "latest", "news", "research", "search", "look up", "find online",
    "check online", "current information", "verify online",
)


def should_handle(message: str) -> bool:
    text = str(message or "").lower()
    return any(trigger in text for trigger in TRIGGERS)


def _source_packet(results: dict) -> list[dict]:
    sources = []
    for result in (results or {}).get("results", [])[:6]:
        sources.append({
            "title": str(result.get("title") or "Untitled")[:300],
            "url": str(result.get("url") or "")[:1200],
            "content": str(result.get("content") or "")[:2500],
        })
    return sources


def _plain_briefing(question: str, sources: list[dict]) -> str:
    if not sources:
        return "External research found no sources. I can't verify this yet."
    lines = ["External research results:", ""]
    for source in sources:
        lines.extend([
            f"- {source['title']}",
            f"  {source['url']}",
            f"  {source['content'][:500]}",
        ])
    return "\n".join(lines)[:12000]


def research(message: str) -> str:
    question = str(message or "").strip()
    tavily_key = os.getenv("TAVILY_API_KEY", "")
    if not tavily_key:
        return "External research is unavailable because its search credential is not configured."

    try:
        search = TavilyClient(api_key=tavily_key).search(
            query=question[:500],
            search_depth="advanced",
            max_results=6,
        )
        sources = _source_packet(search)
    except Exception as exc:
        return f"External research service error: {type(exc).__name__}."

    openai_key = os.getenv("OPENAI_API_KEY", "")
    if not openai_key or not sources:
        return _plain_briefing(question, sources)

    try:
        client = OpenAI(api_key=openai_key)
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Synthesize a concise answer from only the supplied web sources. "
                        "Cite claims with the supplied URLs, preserve disagreement, distinguish "
                        "fact from inference, and state important limitations. Do not mention "
                        "internal agents or claim that unsourced information was verified."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps({"question": question, "sources": sources}, ensure_ascii=False),
                },
            ],
            temperature=0.2,
        )
        return str(response.choices[0].message.content or "").strip()[:12000]
    except Exception:
        return _plain_briefing(question, sources)
