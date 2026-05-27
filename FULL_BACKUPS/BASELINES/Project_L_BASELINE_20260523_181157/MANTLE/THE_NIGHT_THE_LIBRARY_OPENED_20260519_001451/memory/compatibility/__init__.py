# ============================================================
# EVOLUTION ENGINE
# AODS-99
# ============================================================

import json
from pathlib import Path
from datetime import datetime

ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

STATE_FILE = (
    ROOT
    / "evolution"
    / "evolution_state.json"
)

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
            "EVOLUTION LOAD ERROR:",
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
            "EVOLUTION SAVE ERROR:",
            e
        )

def log_milestone(title, detail):

    state = load_state()

    milestones = state.get(
        "milestones",
        []
    )

    milestones.append({

        "title": title,

        "detail": detail,

        "timestamp": str(
            datetime.now()
        )
    })

    state["milestones"] = milestones[-100:]

    save_state(state)

def evolution_status():

    state = load_state()

    return {

        "status": "online",

        "milestones": len(
            state.get(
                "milestones",
                []
            )
        ),

        "operation": "AODS99"
    }


