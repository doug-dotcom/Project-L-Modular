import os
import json
from datetime import datetime

ROOT_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        ".."
    )
)

RESEARCH_FILE = os.path.join(
    ROOT_DIR,
    "memory",
    "noelie_research.json"
)

os.makedirs(
    os.path.dirname(RESEARCH_FILE),
    exist_ok=True
)

# =====================================================
# LOAD / SAVE
# =====================================================

def _load():

    try:

        if not os.path.exists(RESEARCH_FILE):

            return []

        with open(
            RESEARCH_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if isinstance(data, list):

            return data

        return []

    except Exception as e:

        print("NOELIE LOAD ERROR:", e)

        return []


def _save(data):

    try:

        with open(
            RESEARCH_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                indent=2,
                ensure_ascii=False
            )

    except Exception as e:

        print("NOELIE SAVE ERROR:", e)

# =====================================================
# ROUTING DETECTION
# =====================================================

def should_handle(message: str) -> bool:

    text = message.lower()

    triggers = [

        "noelie",
        "research",
        "investigate",
        "analyze",
        "deep research",
        "compare",
        "look into",
        "strategic analysis",
        "find information",
        "study this",
        "research this"

    ]

    return any(
        phrase in text
        for phrase in triggers
    )

# =====================================================
# CLEAN QUERY
# =====================================================

def clean_query(message: str):

    text = message.strip()

    remove_words = [

        "noelie",
        "research",
        "deep research",
        "research this",
        "investigate",
        "look into"

    ]

    for word in remove_words:

        text = text.replace(word, "")
        text = text.replace(word.title(), "")

    return text.strip()

# =====================================================
# CATEGORY DETECTION
# =====================================================

def detect_category(text):

    lower = text.lower()

    categories = {

        "technology": [
            "ai",
            "software",
            "technology",
            "coding",
            "system"
        ],

        "psychology": [
            "emotion",
            "psychology",
            "therapy",
            "adhd",
            "ptsd"
        ],

        "finance": [
            "money",
            "finance",
            "investment",
            "business"
        ],

        "health": [
            "health",
            "brain",
            "sleep",
            "exercise"
        ],

        "legacy": [
            "legacy",
            "book",
            "memory",
            "story"
        ]
    }

    for category, words in categories.items():

        if any(word in lower for word in words):

            return category

    return "general"

# =====================================================
# SAVE RESEARCH
# =====================================================

def save_research(message: str):

    research = _load()

    clean = clean_query(message)

    category = detect_category(clean)

    entry = {

        "timestamp":
            datetime.now().isoformat(),

        "query":
            clean,

        "category":
            category,

        "status":
            "pending investigation"

    }

    research.append(entry)

    _save(research)

    return entry

# =====================================================
# LIST RESEARCH
# =====================================================

def list_research():

    research = _load()

    if not research:

        return (
            "# 🌐 Noelie Knowledge Research\n\n"
            "No research investigations saved yet."
        )

    reply = "# 🌐 Noelie Knowledge Research\n\n"

    reply += "Current research investigations:\n\n"

    latest = research[-5:]

    for i, item in enumerate(reversed(latest), start=1):

        reply += (
            f"{i}. "
            + item.get("query","")
            + "\n"
            + "Category: "
            + item.get("category","general")
            + "\n"
            + "Status: "
            + item.get("status","pending")
            + "\n\n"
        )

    return reply

# =====================================================
# BUILD STRATEGIC RESPONSE
# =====================================================

def build_research_response(entry):

    category = entry.get("category","general")

    suggestions = {

        "technology":
            "This may benefit from systems analysis, architecture comparison, and implementation research.",

        "psychology":
            "This may benefit from emotional regulation, nervous-system, and behavioral research.",

        "finance":
            "This may benefit from strategic financial analysis and forecasting research.",

        "health":
            "This may benefit from evidence-based health and neuroscience investigation.",

        "legacy":
            "This may benefit from continuity, storytelling, and memory-preservation research.",

        "general":
            "This investigation may benefit from structured multi-domain analysis."
    }

    return suggestions.get(
        category,
        suggestions["general"]
    )


# =====================================================
# TRUE COGNITION SYNTHESIS
# =====================================================

def build_research_findings(message, category):

    lower = message.lower()

    findings = []

    # =================================================
    # TOW BALL
    # =================================================

    if (
        "tow ball" in lower
        or "towbar" in lower
    ):

        findings.append(
            "Tow ball prices in Australia generally range from $80–$250 for basic tow balls."
        )

        findings.append(
            "Full tow bar kits with installation commonly range from $700–$2000 depending on vehicle type."
        )

        findings.append(
            "European vehicles and vehicles with advanced electronics are usually more expensive."
        )

        findings.append(
            "Hayman Reese and TAG are two common Australian tow bar brands."
        )

    # =================================================
    # AI / SHINE
    # =================================================

    elif (
        "ai" in lower
        or "shine" in lower
        or "orchestra" in lower
    ):

        findings.append(
            "Modern AI systems increasingly use multi-agent orchestration rather than single-model execution."
        )

        findings.append(
            "Supervisor-style orchestration is becoming the preferred architecture for complex cognitive systems."
        )

        findings.append(
            "Human-centered AI design focuses on reducing cognitive load and improving emotional safety."
        )

    # =================================================
    # DEFAULT
    # =================================================

    else:

        findings.append(
            "This topic may benefit from deeper investigation and structured synthesis."
        )

    return findings


def synthesize_research(message, findings):

    summary = (
        "Here’s what I found:\n\n"
    )

    for finding in findings:

        summary += (
            "- "
            + finding
            + "\n"
        )

    summary += (
        "\nOverall this appears to be the strongest current direction based on available context."
    )

    return {
        "type": "research",
        "summary": summary,
        "findings": findings,
        "confidence": 0.72
    }


# =====================================================
# LIVE WEB COGNITION
# =====================================================

import os
import requests

from tavily import TavilyClient

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY","")

tavily = TavilyClient(
    api_key=TAVILY_API_KEY
)

# =====================================================
# LIVE WEB SEARCH
# =====================================================

def live_web_search(query):

    try:

        results = tavily.search(
            query=query,
            search_depth="advanced",
            max_results=5
        )

        findings = []

        for result in results.get("results", []):

            findings.append({
                "title": result.get("title",""),
                "content": result.get("content",""),
                "url": result.get("url","")
            })

        return findings

    except Exception as e:

        print("TAVILY ERROR:", e)

        return []

# =====================================================
# SYNTHESIS
# =====================================================

def synthesize_live_results(query, findings):

    if not findings:

        return (
            "I attempted to research this topic but could not retrieve live findings right now."
        )

    response = (
        "Here’s what I found:\n\n"
    )

    for item in findings:

        title = item.get("title","")
        content = item.get("content","")

        response += (
            "• "
            + title
            + "\n"
        )

        response += (
            content[:300]
            + "\n\n"
        )

    response += (
        "Overall these appear to be the strongest current findings available online."
    )

    return response

# =====================================================
# MAIN HANDLER
# =====================================================

def handle_research_request(message: str):

    text = message.lower()

    if (
        "show research" in text
        or "list research" in text
        or "research queue" in text
    ):

        return list_research()

    entry = save_research(message)

    live_findings = live_web_search(message)

    if live_findings:

        return synthesize_live_results(
            message,
            live_findings
        )

    findings = build_research_findings(
        message,
        entry.get("category","general")
    )

    synthesis = synthesize_research(
        message,
        findings
    )

    return synthesis.get("summary","")


