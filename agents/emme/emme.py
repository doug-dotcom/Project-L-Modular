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

STATE_FILE = os.path.join(
    ROOT_DIR,
    "memory",
    "emme_states.json"
)

os.makedirs(
    os.path.dirname(STATE_FILE),
    exist_ok=True
)

# =====================================================
# LOAD / SAVE
# =====================================================

def _load():

    try:

        if not os.path.exists(STATE_FILE):

            return []

        with open(
            STATE_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if isinstance(data, list):

            return data

        return []

    except Exception as e:

        print("EMME LOAD ERROR:", e)

        return []


def _save(data):

    try:

        with open(
            STATE_FILE,
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

        print("EMME SAVE ERROR:", e)

# =====================================================
# DETECT HANDLE
# =====================================================

def should_handle(message: str) -> bool:

    text = message.lower()

    direct_words = [

        "emme",
        "i feel",
        "i am feeling",
        "emotion",
        "overwhelmed",
        "anxious",
        "panic",
        "sad",
        "angry",
        "stressed",
        "emotional support",
        "ground me",
        "help me calm down",
        "nervous system"

    ]

    return any(
        phrase in text
        for phrase in direct_words
    )

# =====================================================
# DETECT EMOTIONAL STATE
# =====================================================

def detect_state(message: str):

    text = message.lower()

    states = {

        "overwhelmed": [
            "overwhelmed",
            "too much",
            "spiraling",
            "shutdown"
        ],

        "anxious": [
            "anxious",
            "panic",
            "worried",
            "fear"
        ],

        "sad": [
            "sad",
            "down",
            "depressed",
            "lonely"
        ],

        "angry": [
            "angry",
            "frustrated",
            "rage",
            "mad"
        ],

        "positive": [
            "grateful",
            "happy",
            "proud",
            "calm",
            "good"
        ]
    }

    for state, words in states.items():

        if any(word in text for word in words):

            return state

    return "unclear"

# =====================================================
# SAVE STATE
# =====================================================

def save_state(message: str):

    states = _load()

    state = detect_state(message)

    entry = {

        "timestamp": datetime.now().isoformat(),

        "state": state,

        "message": message

    }

    states.append(entry)

    _save(states)

    return entry

# =====================================================
# RESPONSE ENGINE
# =====================================================

def build_support_response(state):

    responses = {

        "overwhelmed":
            (
                "Slow down.\n\n"
                "Reduce information density.\n"
                "Focus on one next step only.\n\n"
                "You do not need to solve everything at once."
            ),

        "anxious":
            (
                "You are safe right now.\n\n"
                "Breathe slowly.\n"
                "Stay grounded in the present moment.\n\n"
                "We can move one step at a time."
            ),

        "sad":
            (
                "I hear that you're hurting.\n\n"
                "You do not have to carry everything alone.\n"
                "Let's move gently and calmly together."
            ),

        "angry":
            (
                "Pause before reacting.\n\n"
                "Let's slow the nervous system down first.\n"
                "Clarity comes after regulation."
            ),

        "positive":
            (
                "That’s really good to hear.\n\n"
                "Take a moment to recognize the progress.\n"
                "Small consistent growth matters."
            ),

        "unclear":
            (
                "I’m here with you.\n\n"
                "Tell me more about what’s happening emotionally."
            )
    }

    return responses.get(
        state,
        responses["unclear"]
    )

# =====================================================
# MAIN HANDLER
# =====================================================

def handle_emotional_request(message: str):

    entry = save_state(message)

    state = entry.get("state", "unclear")

    support = build_support_response(state)

    return (
        "# ❤️ Emme Emotional Support\n\n"
        f"Detected emotional state: {state}\n\n"
        + support
    )
