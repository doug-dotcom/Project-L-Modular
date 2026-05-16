import os
import json
import random
from datetime import datetime

ROOT_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        ".."
    )
)

REFLECTION_FILE = os.path.join(
    ROOT_DIR,
    "memory",
    "richie_reflections.json"
)

os.makedirs(
    os.path.dirname(REFLECTION_FILE),
    exist_ok=True
)

# =====================================================
# LOAD / SAVE
# =====================================================

def _load():

    try:

        if not os.path.exists(REFLECTION_FILE):

            return []

        with open(
            REFLECTION_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if isinstance(data, list):

            return data

        return []

    except Exception as e:

        print("RICHIE LOAD ERROR:", e)

        return []


def _save(data):

    try:

        with open(
            REFLECTION_FILE,
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

        print("RICHIE SAVE ERROR:", e)

# =====================================================
# ROUTING DETECTION
# =====================================================

def should_handle(message: str) -> bool:

    text = message.lower()

    triggers = [

        "richie",
        "reflect",
        "reflection",
        "what did i learn",
        "growth",
        "pattern",
        "self awareness",
        "help me reflect",
        "reflective learning",
        "journal",
        "insight"

    ]

    return any(
        phrase in text
        for phrase in triggers
    )

# =====================================================
# REFLECTION QUESTIONS
# =====================================================

QUESTIONS = [

    "What did you learn about yourself today?",

    "What pattern are you beginning to notice?",

    "What helped you feel most aligned recently?",

    "What caused the most emotional friction today?",

    "Where are you evolving intentionally instead of reacting automatically?",

    "What are you proud of right now?",

    "What would help reduce cognitive load this week?",

    "What part of your growth feels most meaningful?",

    "What are you avoiding emotionally or mentally?",

    "What lesson should future-you remember from today?"

]

# =====================================================
# SAVE REFLECTION
# =====================================================

def save_reflection(message: str):

    reflections = _load()

    entry = {

        "timestamp":
            datetime.now().isoformat(),

        "reflection":
            message

    }

    reflections.append(entry)

    _save(reflections)

    return entry

# =====================================================
# BUILD INSIGHT
# =====================================================

def build_insight():

    return random.choice(QUESTIONS)

# =====================================================
# LIST REFLECTIONS
# =====================================================

def list_reflections():

    reflections = _load()

    if not reflections:

        return (
            "# 🪞 Richie Reflective Learning\n\n"
            "No reflections saved yet."
        )

    reply = "# 🪞 Richie Reflective Learning\n\n"

    reply += "Recent reflections:\n\n"

    latest = reflections[-5:]

    for i, item in enumerate(reversed(latest), start=1):

        reply += (
            f"## Reflection {i}\n"
            + item.get("reflection","")
            + "\n\n"
        )

    return reply

# =====================================================
# MAIN HANDLER
# =====================================================

def handle_reflection_request(message: str):

    text = message.lower()

    if (
        "show reflections" in text
        or "list reflections" in text
    ):

        return list_reflections()

    if (
        "question" in text
        or "reflect" in text
        or "insight" in text
    ):

        question = build_insight()

        return (
            "# 🪞 Richie Reflective Learning\n\n"
            "Reflection Prompt:\n\n"
            + question
        )

    entry = save_reflection(message)

    return (
        "# 🪞 Richie Reflective Learning\n\n"
        "Reflection saved successfully.\n\n"
        "Saved Reflection:\n\n"
        + entry.get("reflection","")
    )
