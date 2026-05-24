# ============================================================
# LOCAL RUNTIME CONTINUITY ENGINE
# AODS-85
# ============================================================

import json
from pathlib import Path
from datetime import datetime

ROOT = Path(r"C:\Shine_L")

CONTINUITY_FILE = (
    ROOT
    / "memory"
    / "continuity"
    / "continuity_state.json"
)

def load_state():

    try:

        if not CONTINUITY_FILE.exists():

            return {}

        return json.loads(
            CONTINUITY_FILE.read_text(
                encoding="utf-8"
            )
        )

    except Exception as e:

        print(
            "CONTINUITY LOAD ERROR:",
            e
        )

        return {}

def save_state(state):

    try:

        state["last_updated"] = str(
            datetime.now()
        )

        CONTINUITY_FILE.write_text(
            json.dumps(
                state,
                indent=2,
                ensure_ascii=False
            ),
            encoding="utf-8"
        )

    except Exception as e:

        print(
            "CONTINUITY SAVE ERROR:",
            e
        )

def process(user_msg):

    state = load_state()

    recent = state.get(
        "recent_topics",
        []
    )

    recent.append(str(user_msg))

    recent = recent[-10:]

    state["recent_topics"] = recent

    save_state(state)

    return state

def build_context():

    state = load_state()

    topics = state.get(
        "recent_topics",
        []
    )

    compressed = compress_recent_topics(
        topics
    )

    if not compressed:

        return ""

    return (
        "RECENT CONTINUITY:\n"
        + compressed
    )

def runtime_status():

    return {
        "status": "online",
        "engine": "local_runtime",
        "continuity_file": str(
            CONTINUITY_FILE
        )
    }



# ============================================================
# RUNTIME CONVERSATION COMPRESSION
# ============================================================

def compress_recent_topics(topics):

    try:

        if not topics:
            return ""

        cleaned = []

        for item in topics[-10:]:

            text = str(item).strip()

            if not text:
                continue

            if text not in cleaned:
                cleaned.append(text)

        if not cleaned:
            return ""

        return (
            "Recent conversation summary:\n"
            + "\n".join(
                "- " + x
                for x in cleaned[-6:]
            )
        )

    except Exception as e:

        print(
            "CONTINUITY COMPRESSION ERROR:",
            e
        )

        return ""

