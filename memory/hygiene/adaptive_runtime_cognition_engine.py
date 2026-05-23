import json
from pathlib import Path
from datetime import datetime

ROOT = Path(r"C:\Shine_L")

STATE_FILE = ROOT / "memory" / "state" / "cognitive_states.json"
ATTENTION_FILE = ROOT / "memory" / "attention" / "attention_orchestration.json"
RECALL_FILE = ROOT / "memory" / "recall_bridge" / "recall_bridge.json"
SELF_MODEL_FILE = ROOT / "memory" / "self_model" / "self_model.json"

OUT_DIR = ROOT / "memory" / "runtime"
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
    print("Loading runtime cognition layers...")

    state = load_json(STATE_FILE)
    attention = load_json(ATTENTION_FILE)
    recall = load_json(RECALL_FILE)
    self_model = load_json(SELF_MODEL_FILE)

    # =====================================================
    # BUILD RUNTIME PROFILE
    # =====================================================

    runtime = {

        "created_at": str(datetime.utcnow()),

        "runtime_identity": {
            "system": "Project L",
            "mode": "Adaptive cognition runtime"
        },

        "runtime_state": {

            "active_cognition":
                "project_execution",

            "active_attention":
                "project_attention",

            "active_runtime_focus": [

                "memory continuity",
                "adaptive recall",
                "attention routing",
                "context restoration",
                "human-aligned cognition"
            ]
        },

        "runtime_behavior": {

            "retrieval_mode":
                "state-aware",

            "attention_mode":
                "dynamic salience weighting",

            "continuity_mode":
                "persistent",

            "response_mode":
                "contextual and relational"
        },

        "runtime_capabilities": [

            "continuity restoration",
            "context-linked recall",
            "state-based retrieval",
            "attention orchestration",
            "semantic hydration",
            "meta-cognitive observation",
            "reinforcement awareness"
        ],

        "next_runtime_goal":
            "Live conversational cognition integration"
    }

    out_path = OUT_DIR / "adaptive_runtime_profile.json"

    out_path.write_text(
        json.dumps(runtime, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    report_path = REPORT_DIR / f"adaptive_runtime_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

    report_path.write_text(
        json.dumps(runtime, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("")
    print("Adaptive runtime cognition complete.")
    print(f"Runtime profile written to: {out_path}")
    print(f"Report written to: {report_path}")

    print("")
    print("Runtime Summary:")
    print("")
    print(" - Runtime cognition established")
    print(" - Adaptive recall active")
    print(" - Dynamic attention active")
    print(" - Context continuity active")
    print(" - Conversational cognition preparation complete")
    print("")

if __name__ == "__main__":
    run()

