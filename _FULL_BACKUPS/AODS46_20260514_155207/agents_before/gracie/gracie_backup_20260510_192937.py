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

LEGACY_FILE = os.path.join(
    ROOT_DIR,
    "memory",
    "gracie_legacy.json"
)

os.makedirs(
    os.path.dirname(LEGACY_FILE),
    exist_ok=True
)

# =====================================================
# LOAD / SAVE
# =====================================================

def _load():

    try:

        if not os.path.exists(LEGACY_FILE):

            return []

        with open(
            LEGACY_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if isinstance(data, list):

            return data

        return []

    except Exception as e:

        print("GRACIE LOAD ERROR:", e)

        return []


def _save(data):

    try:

        with open(
            LEGACY_FILE,
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

        print("GRACIE SAVE ERROR:", e)

# =====================================================
# ROUTING DETECTION
# =====================================================

def should_handle(message: str) -> bool:

    text = message.lower()

    triggers = [

        "gracie",
        "legacy",
        "story",
        "life lesson",
        "book memory",
        "save this story",
        "family memory",
        "future generations",
        "preserve this",
        "legacy builder",
        "write this down"

    ]

    return any(
        phrase in text
        for phrase in triggers
    )

# =====================================================
# CLEAN STORY
# =====================================================

def clean_story(message: str):

    text = message.strip()

    remove_words = [

        "gracie",
        "legacy",
        "save this story",
        "write this down",
        "legacy builder"

    ]

    for word in remove_words:

        text = text.replace(word, "")
        text = text.replace(word.title(), "")

    return text.strip()

# =====================================================
# DETECT THEMES
# =====================================================

def detect_themes(text):

    lower = text.lower()

    themes = []

    theme_map = {

        "family": [
            "kids",
            "children",
            "family",
            "father",
            "dad",
            "grandchildren"
        ],

        "recovery": [
            "recovery",
            "na",
            "aa",
            "clean",
            "sober"
        ],

        "growth": [
            "learned",
            "growth",
            "wisdom",
            "lesson"
        ],

        "legacy": [
            "legacy",
            "future",
            "remember",
            "story"
        ],

        "shine": [
            "shine",
            "ecosystem",
            "l",
            "agents"
        ]
    }

    for theme, words in theme_map.items():

        if any(word in lower for word in words):

            themes.append(theme)

    return themes

# =====================================================
# SAVE LEGACY ENTRY
# =====================================================

def save_story(message: str):

    stories = _load()

    clean = clean_story(message)

    entry = {

        "timestamp":
            datetime.now().isoformat(),

        "story":
            clean,

        "themes":
            detect_themes(clean)

    }

    stories.append(entry)

    _save(stories)

    return entry

# =====================================================
# LIST STORIES
# =====================================================

def list_stories():

    stories = _load()

    if not stories:

        return (
            "# 📖 Gracie Legacy Builder\n\n"
            "No legacy stories saved yet."
        )

    reply = "# 📖 Gracie Legacy Builder\n\n"

    reply += "Recent legacy entries:\n\n"

    latest = stories[-5:]

    for i, item in enumerate(reversed(latest), start=1):

        reply += (
            f"## Story {i}\n"
            + item.get("story","")
            + "\n\nThemes: "
            + ", ".join(item.get("themes", []))
            + "\n\n"
        )

    return reply

# =====================================================
# MAIN HANDLER
# =====================================================

def handle_legacy_request(message: str):

    text = message.lower()

    if (
        "show stories" in text
        or "show legacy" in text
        or "list stories" in text
    ):

        return list_stories()

    entry = save_story(message)

    return (
        "# 📖 Gracie Legacy Builder\n\n"
        "Legacy story saved successfully.\n\n"
        "Story:\n\n"
        + entry.get("story","")
        + "\n\nThemes: "
        + ", ".join(entry.get("themes", []))
    )
