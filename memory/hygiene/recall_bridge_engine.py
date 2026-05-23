import json
from pathlib import Path
from datetime import datetime

ROOT = Path(r"C:\Shine_L")

CONTINUITY_FILE = ROOT / "memory" / "continuity" / "continuity_anchor.json"
SELF_MODEL_FILE = ROOT / "memory" / "self_model" / "self_model.json"
META_FILE = ROOT / "memory" / "metacognition" / "metacognition_report.json"
ACTIVE_PRIORITY_FILE = ROOT / "memory" / "priority" / "active_priority_memory.json"

OUT_DIR = ROOT / "memory" / "recall_bridge"
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
    print("Loading continuity systems...")

    continuity = load_json(CONTINUITY_FILE)
    self_model = load_json(SELF_MODEL_FILE)
    meta = load_json(META_FILE)
    priority = load_json(ACTIVE_PRIORITY_FILE)

    # =====================================================
    # BUILD RECALL BRIDGE
    # =====================================================

    bridge = {

        "created_at": str(datetime.utcnow()),

        "resume_identity": {
            "system_name": "Project L",
            "current_role": "Cognitive memory orchestration system",
            "current_focus": "Continuity-aware cognition"
        },

        "resume_state": continuity.get(
            "current_operating_mode",
            {}
        ),

        "resume_context": {

            "what_is_happening":
                "Project L is evolving from memory storage into active cognition architecture.",

            "current_phase":
                "Attention, meta-cognition, continuity, and recall orchestration.",

            "primary_focus":
                "Building human-like contextual retrieval and continuity.",

            "active_pathway":
                "Project L architecture remains dominant reinforced cognition pathway."
        },

        "live_resume_prompt": [

            "Reconnect continuity anchors.",
            "Load dominant cognition state.",
            "Restore active attention pathways.",
            "Hydrate active project context.",
            "Resume prior cognitive direction safely."
        ],

        "active_observations":
            meta.get(
                "metacognition",
                {}
            ).get(
                "observations",
                []
            ),

        "next_evolutionary_layer":
            "Adaptive Runtime Cognition Engine"
    }

    out_path = OUT_DIR / "recall_bridge.json"

    out_path.write_text(
        json.dumps(bridge, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    report_path = REPORT_DIR / f"recall_bridge_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

    report_path.write_text(
        json.dumps(bridge, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("")
    print("Recall bridge engine complete.")
    print(f"Bridge written to: {out_path}")
    print(f"Report written to: {report_path}")

    print("")
    print("Recall Summary:")
    print("")
    print(" - Continuity bridge established")
    print(" - Active cognition restored")
    print(" - Recall hydration enabled")
    print(" - Project context linked")
    print(" - Ready for adaptive runtime cognition")
    print("")

if __name__ == "__main__":
    run()

