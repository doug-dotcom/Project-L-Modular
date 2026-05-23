import json
from pathlib import Path
from datetime import datetime

ROOT = Path(r"C:\Shine_L")

STATE_FILE = ROOT / "memory" / "state" / "cognitive_states.json"
ATTENTION_FILE = ROOT / "memory" / "attention" / "attention_orchestration.json"
REINFORCEMENT_FILE = ROOT / "memory" / "reinforcement" / "reinforcement_map.json"

OUT_DIR = ROOT / "memory" / "metacognition"
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
    print("Loading cognition systems...")

    states = load_json(STATE_FILE)
    attention = load_json(ATTENTION_FILE)
    reinforcement = load_json(REINFORCEMENT_FILE)

    meta = {}

    # =====================================================
    # STATE ANALYSIS
    # =====================================================

    state_summary = states.get("states", {})

    dominant_state = None
    dominant_value = 0

    for k, v in state_summary.items():

        activation = v.get("activation_strength", 0)

        if activation > dominant_value:
            dominant_value = activation
            dominant_state = k

    meta["dominant_state"] = {
        "state": dominant_state,
        "activation": dominant_value
    }

    # =====================================================
    # ATTENTION ANALYSIS
    # =====================================================

    attention_summary = attention.get(
        "attention_summary", {}
    )

    dominant_attention = None
    attention_value = 0

    for k, v in attention_summary.items():

        strength = v.get(
            "attention_strength", 0
        )

        if strength > attention_value:
            attention_value = strength
            dominant_attention = k

    meta["dominant_attention"] = {
        "attention_type": dominant_attention,
        "strength": attention_value
    }

    # =====================================================
    # REINFORCEMENT ANALYSIS
    # =====================================================

    reinforcement_summary = reinforcement.get(
        "summary", {}
    )

    dominant_loop = None
    loop_strength = 0

    for k, v in reinforcement_summary.items():

        strength = v.get(
            "reinforcement_strength", 0
        )

        if strength > loop_strength:
            loop_strength = strength
            dominant_loop = k

    meta["dominant_reinforcement_loop"] = {
        "loop": dominant_loop,
        "strength": loop_strength
    }

    # =====================================================
    # COGNITIVE OBSERVATIONS
    # =====================================================

    observations = []

    if dominant_state == "project_execution":
        observations.append(
            "Cognition currently biased toward execution and system building."
        )

    if dominant_attention == "project_attention":
        observations.append(
            "Attention heavily focused on Project L architecture."
        )

    if dominant_loop == "project_l_core":
        observations.append(
            "Project L is currently the strongest reinforced cognition pathway."
        )

    if dominant_loop == "identity_loop":
        observations.append(
            "Identity processing remains highly active."
        )

    if dominant_loop == "future_fear":
        observations.append(
            "Future-oriented stress loops remain active."
        )

    meta["observations"] = observations

    output = {
        "created_at": str(datetime.utcnow()),
        "metacognition": meta
    }

    out_path = OUT_DIR / "metacognition_report.json"

    out_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    report_path = REPORT_DIR / f"metacognition_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

    report_path.write_text(
        json.dumps(output, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("")
    print("Meta-cognition engine complete.")
    print(f"Report written to: {report_path}")

    print("")
    print("Meta Summary:")
    print("")

    for obs in observations:
        print(f" - {obs}")

    print("")

if __name__ == "__main__":
    run()

