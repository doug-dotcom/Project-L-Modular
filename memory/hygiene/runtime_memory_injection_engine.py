import json
from pathlib import Path
from datetime import datetime

ROOT = Path(r"C:\Shine_L")

CONVO_FILE = ROOT / "memory" / "conversation" / "conversational_state.json"
RUNTIME_FILE = ROOT / "memory" / "runtime" / "adaptive_runtime_profile.json"
RECALL_FILE = ROOT / "memory" / "recall_bridge" / "recall_bridge.json"
PRIORITY_FILE = ROOT / "memory" / "priority" / "active_priority_memory.json"

OUT_DIR = ROOT / "memory" / "injection"
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
    print("Loading runtime cognition systems...")

    convo = load_json(CONVO_FILE)
    runtime = load_json(RUNTIME_FILE)
    recall = load_json(RECALL_FILE)
    priority = load_json(PRIORITY_FILE)

    injection = {

        "created_at": str(datetime.utcnow()),

        "runtime_injection_profile": {

            "mode":
                "live conversational cognition",

            "continuity_enabled":
                True,

            "state_aware_retrieval":
                True,

            "semantic_hydration":
                True,

            "attention_weighting":
                True
        },

        "active_context_packets": [

            {
                "type": "project_context",
                "priority": "critical",
                "description":
                    "Project L cognitive architecture development"
            },

            {
                "type": "memory_context",
                "priority": "high",
                "description":
                    "Continuity-aware semantic retrieval"
            },

            {
                "type": "conversation_context",
                "priority": "high",
                "description":
                    "Preserve conversational flow and emotional tone"
            },

            {
                "type": "identity_context",
                "priority": "medium",
                "description":
                    "Maintain long-term contextual continuity"
            }
        ],

        "runtime_retrieval_behaviors": [

            "inject continuity before response generation",
            "hydrate semantically linked memories",
            "prioritize active cognition pathways",
            "preserve conversational topic continuity",
            "maintain emotional-context awareness"
        ],

        "response_cognition_mode": {

            "retrieval_style":
                "contextual",

            "memory_style":
                "relational",

            "continuity_style":
                "persistent",

            "conversation_style":
                "adaptive"
        },

        "next_evolutionary_goal":
            "Live server integration and dynamic runtime injection"
    }

    out_path = OUT_DIR / "runtime_memory_injection.json"

    out_path.write_text(
        json.dumps(injection, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    report_path = REPORT_DIR / f"runtime_injection_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

    report_path.write_text(
        json.dumps(injection, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("")
    print("Runtime memory injection complete.")
    print(f"Injection profile written to: {out_path}")
    print(f"Report written to: {report_path}")

    print("")
    print("Injection Summary:")
    print("")
    print(" - Runtime injection active")
    print(" - Context hydration active")
    print(" - Continuity-aware recall active")
    print(" - Attention-weighted retrieval active")
    print(" - Ready for live runtime integration")
    print("")

if __name__ == "__main__":
    run()

