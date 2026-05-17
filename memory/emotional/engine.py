# ============================================================
# EMOTIONAL CONTEXT ENGINE
# AODS-97
# ============================================================

import json
from pathlib import Path
from datetime import datetime

ROOT = Path(r"C:\Shine_L")

STATE_FILE = (
    ROOT
    / "memory"
    / "emotional"
    / "emotional_state.json"
)

EMOTION_PATTERNS = {

    "positive": [
        "excited",
        "grateful",
        "happy",
        "motivated",
        "good"
    ],

    "fatigued": [
        "tired",
        "flat",
        "drained",
        "exhausted"
    ],

    "stressed": [
        "overwhelmed",
        "stressed",
        "pressure",
        "hard"
    ],

    "connected": [
        "crew",
        "connection",
        "supported",
        "together"
    ]
}

def load_state():

    try:

        if not STATE_FILE.exists():
            return {}

        return json.loads(
            STATE_FILE.read_text(
                encoding="utf-8"
            )
        )

    except Exception as e:

        print(
            "EMOTIONAL LOAD ERROR:",
            e
        )

        return {}

def save_state(data):

    try:

        STATE_FILE.write_text(
            json.dumps(
                data,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

    except Exception as e:

        print(
            "EMOTIONAL SAVE ERROR:",
            e
        )

def process_emotional_context(text):

    try:

        text_lower = str(text).lower()

        state = load_state()

        detected = []

        for emotion, triggers in EMOTION_PATTERNS.items():

            for trigger in triggers:

                if trigger in text_lower:

                    detected.append(emotion)

                    break

        state["recent_emotions"] = detected[-5:]

        state["last_updated"] = str(
            datetime.now()
        )

        save_state(state)

        return detected

    except Exception as e:

        print(
            "EMOTIONAL PROCESS ERROR:",
            e
        )

        return []

def build_emotional_context():

    try:

        state = load_state()

        emotions = state.get(
            "recent_emotions",
            []
        )

        if not emotions:
            return ""

        return (
            "Recent emotional context: "
            + ", ".join(emotions)
        )

    except Exception as e:

        print(
            "EMOTIONAL CONTEXT ERROR:",
            e
        )

        return ""

def emotional_status():

    return {

        "status": "online",

        "operation": "AODS97",

        "state_file": str(
            STATE_FILE
        )
    }
