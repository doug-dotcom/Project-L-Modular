import json
from pathlib import Path
from datetime import datetime

ROOT = Path(r"C:\Shine_L")

META_FILE = ROOT / "memory" / "metacognition" / "metacognition_report.json"
STATE_FILE = ROOT / "memory" / "state" / "cognitive_states.json"
REINFORCEMENT_FILE = ROOT / "memory" / "reinforcement" / "reinforcement_map.json"
ATTENTION_FILE = ROOT / "memory" / "attention" / "attention_orchestration.json"

OUT_DIR = ROOT / "memory" / "self_model"
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
    print("Loading cognition layers...")

    meta = load_json(META_FILE)
    state = load_json(STATE_FILE)
    reinforcement = load_json(REINFORCEMENT_FILE)
    attention = load_json(ATTENTION_FILE)

    # =====================================================
    # BUILD SELF MODEL
    # =====================================================

    self_model = {

        "identity": {
            "name": "Project L",
            "type": "Cognitive Memory Architecture",
            "purpose": "Human-aligned contextual cognition and memory continuity"
        },

        "dominant_state":
            meta.get(
                "metacognition",
                {}
            ).get(
                "dominant_state",
                {}
            ),

        "dominant_attention":
            meta.get(
                "metacognition",
                {}
            ).get(
                "dominant_attention",
                {}
            ),

        "dominant_reinforcement":
            meta.get(
                "metacognition",
                {}
            ).get(
                "dominant_reinforcement_loop",
                {}
            ),

        "behavioral_profile": {

            "strongest_focus":
                "Project L architecture and cognition systems",

            "secondary_focus":
                "Identity processing and recovery regulation",

            "retrieval_style":
                "State-dependent semantic retrieval",

            "attention_style":
                "Dynamic salience-weighted cognition",

            "memory_style":
                "Relational and contextual"
        },

        "current_biases": [

            "Project-oriented cognition",
            "High reinforcement toward system building",
            "Identity and meaning processing active",
            "Recovery-oriented emotional regulation"
        ],

        "observations":
            meta.get(
                "metacognition",
                {}
            ).get(
                "observations",
                []
            )
    }

    output = {
        "created_at": str(datetime.utcnow()),
        "self_model": self_model
    }

    out_path = OUT_DIR / "self_model.json"

    out_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    report_path = REPORT_DIR / f"self_model_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

    report_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("")
    print("Self-model engine complete.")
    print(f"Report written to: {report_path}")

    print("")
    print("Self Summary:")
    print("")

    print(
        " - Purpose: Human-aligned cognition"
    )

    print(
        " - Dominant cognition: Project execution"
    )

    print(
        " - Retrieval style: State-dependent"
    )

    print(
        " - Attention style: Dynamic orchestration"
    )

    print(
        " - Memory style: Relational/contextual"
    )

    print("")

if __name__ == "__main__":
    run()

