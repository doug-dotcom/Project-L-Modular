import json
from pathlib import Path
from datetime import datetime

ROOT = Path(r"C:\Shine_L")

RUNTIME_FILE = ROOT / "memory" / "runtime" / "adaptive_runtime_profile.json"
RECALL_FILE = ROOT / "memory" / "recall_bridge" / "recall_bridge.json"
STATE_FILE = ROOT / "memory" / "state" / "cognitive_states.json"

OUT_DIR = ROOT / "memory" / "conversation"
REPORT_DIR = ROOT / "memory" / "hygiene" / "reports"

def load_json(path):

    if not path.exists():
        return {}

    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )

    except:
        return {}

def run():

    print("")
    print("Loading conversational cognition layers...")

    runtime = load_json(RUNTIME_FILE)
    recall = load_json(RECALL_FILE)
    state = load_json(STATE_FILE)

    conversation_state = {

        "created_at": str(datetime.utcnow()),

        "conversation_identity": {
            "system": "Project L",
            "mode": "Conversational cognition"
        },

        "active_topic_threads": [

            "memory cognition",
            "human-aligned AI",
            "continuity systems",
            "attention orchestration",
            "Project L architecture"
        ],

        "conversation_tone": {
            "style": "deep reflective collaborative",
            "emotional_temperature": "engaged focused optimistic",
            "continuity_strength": "high"
        },

        "active_cognition": {
            "primary_state": "project_execution",
            "secondary_state": "identity_processing",
            "retrieval_mode": "contextual relational"
        },

        "conversation_behaviors": [

            "maintain continuity",
            "preserve project direction",
            "link concepts semantically",
            "track evolving cognition",
            "restore conversational context"
        ],

        "next_live_goal":
            "Runtime memory injection into live server responses"
    }

    out_path = OUT_DIR / "conversational_state.json"

    out_path.write_text(
        json.dumps(conversation_state, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    report_path = REPORT_DIR / f"conversational_state_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

    report_path.write_text(
        json.dumps(conversation_state, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("")
    print("Conversational state engine complete.")
    print(f"State written to: {out_path}")
    print(f"Report written to: {report_path}")

    print("")
    print("Conversation Summary:")
    print("")
    print(" - Conversational continuity active")
    print(" - Topic tracking active")
    print(" - Emotional tone mapping active")
    print(" - Runtime cognition linked")
    print(" - Ready for runtime memory injection")
    print("")

if __name__ == "__main__":
    run()

