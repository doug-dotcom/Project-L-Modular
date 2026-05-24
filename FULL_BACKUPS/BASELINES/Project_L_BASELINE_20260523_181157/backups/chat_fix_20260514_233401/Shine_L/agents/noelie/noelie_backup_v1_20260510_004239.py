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

    strategy = build_research_response(entry)

    return (
        "# 🌐 Noelie Knowledge Research\n\n"
        "Research investigation created successfully.\n\n"
        "Research Topic:\n"
        + entry.get("query","")
        + "\n\nCategory: "
        + entry.get("category","general")
        + "\n\nStrategic Insight:\n"
        + strategy
    )
