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

ORCH_FILE = os.path.join(
    ROOT_DIR,
    "memory",
    "tegan_orchestration.json"
)

os.makedirs(
    os.path.dirname(ORCH_FILE),
    exist_ok=True
)

# =====================================================
# LOAD / SAVE
# =====================================================

def _load():

    try:

        if not os.path.exists(ORCH_FILE):

            return []

        with open(
            ORCH_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if isinstance(data, list):

            return data

        return []

    except Exception as e:

        print("TEGAN LOAD ERROR:", e)

        return []


def _save(data):

    try:

        with open(
            ORCH_FILE,
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

        print("TEGAN SAVE ERROR:", e)

# =====================================================
# ROUTING DETECTION
# =====================================================

def should_handle(message: str) -> bool:

    text = message.lower()

    triggers = [

        "tegan",
        "ecosystem",
        "orchestrate",
        "coordination",
        "system overview",
        "agent overview",
        "integration",
        "workflow",
        "how are the agents working",
        "ecosystem status",
        "coordinate agents"

    ]

    return any(
        phrase in text
        for phrase in triggers
    )

# =====================================================
# AGENT STATUS
# =====================================================

AGENTS = {

    "Millie":
        "Memory & continuity",

    "Emme":
        "Emotional regulation",

    "Addie":
        "Task execution",

    "Gracie":
        "Legacy preservation",

    "Noelie":
        "Knowledge research",

    "Richie":
        "Reflective learning"

}

# =====================================================
# SAVE ORCHESTRATION EVENT
# =====================================================

def save_event(message):

    events = _load()

    entry = {

        "timestamp":
            datetime.now().isoformat(),

        "event":
            message

    }

    events.append(entry)

    _save(events)

    return entry

# =====================================================
# BUILD ECOSYSTEM REPORT
# =====================================================

def build_report():

    reply = "# 🔗 Tegan Integration Spine\n\n"

    reply += (
        "The Shine ecosystem is online and coordinated.\n\n"
    )

    reply += "## Active Agents\n\n"

    for name, role in AGENTS.items():

        reply += (
            f"- {name} → {role}\n"
        )

    reply += "\n## System Function\n\n"

    reply += (
        "Tegan coordinates:\n"
        "- cognition routing\n"
        "- workflow orchestration\n"
        "- context synchronization\n"
        "- ecosystem continuity\n"
        "- multi-agent collaboration\n"
    )

    reply += "\n## Ecosystem Status\n\n"

    reply += (
        "The ecosystem is stable and evolving coherently."
    )

    return reply

# =====================================================
# MAIN HANDLER
# =====================================================

def handle_integration_request(message: str):

    save_event(message)

    return build_report()
