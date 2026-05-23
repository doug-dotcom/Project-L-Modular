import json
from pathlib import Path
from datetime import datetime

ROOT = Path(r"C:\Shine_L")

SELF_MODEL_FILE = ROOT / "memory" / "self_model" / "self_model.json"
META_FILE = ROOT / "memory" / "metacognition" / "metacognition_report.json"
STATE_FILE = ROOT / "memory" / "state" / "cognitive_states.json"
ATTENTION_FILE = ROOT / "memory" / "attention" / "attention_orchestration.json"

OUT_DIR = ROOT / "memory" / "continuity"
REPORT_DIR = ROOT / "memory" / "hygiene" / "reports"

def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def run():

    print("")
    print("Loading continuity source layers...")

    self_model = load_json(SELF_MODEL_FILE)
    meta = load_json(META_FILE)
    state = load_json(STATE_FILE)
    attention = load_json(ATTENTION_FILE)

    sm = self_model.get("self_model", {})
    mc = meta.get("metacognition", {})

    anchor = {
        "created_at": str(datetime.utcnow()),

        "current_identity": {
            "name": "Project L",
            "role": "Cognitive memory system",
            "purpose": "Preserve continuity, retrieve meaning, and support human-aligned cognition."
        },

        "current_operating_mode": {
            "dominant_state": mc.get("dominant_state", {}),
            "dominant_attention": mc.get("dominant_attention", {}),
            "dominant_reinforcement_loop": mc.get("dominant_reinforcement_loop", {})
        },

        "continuity_summary": {
            "what_l_is_doing": "Building memory cognition architecture through safe-mode AODS layers.",
            "why_it_matters": "To move from raw memory storage toward contextual, state-aware, relational cognition.",
            "current_phase": "Memory orchestration, attention, meta-cognition, self-modeling, and continuity anchoring.",
            "next_needed_layer": "Recall Bridge Engine: connect continuity anchors into runtime retrieval."
        },

        "resume_prompt": (
            "Resume Project L from continuity anchor. "
            "Review memory/continuity/continuity_anchor.json, "
            "then continue with the next safe-mode AODS layer."
        ),

        "active_principles": [
            "Memory is cognition.",
            "Attention decides what memory becomes active.",
            "State changes retrieval.",
            "Continuity turns data into identity over time.",
            "Safe mode first: observe before modifying core memory."
        ],

        "self_model_snapshot": sm.get("behavioral_profile", {}),

        "metacognitive_observations": mc.get("observations", [])
    }

    out_path = OUT_DIR / "continuity_anchor.json"

    out_path.write_text(
        json.dumps(anchor, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    report_path = REPORT_DIR / f"continuity_anchor_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

    report_path.write_text(
        json.dumps(anchor, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("")
    print("Continuity anchor engine complete.")
    print(f"Anchor written to: {out_path}")
    print(f"Report written to: {report_path}")

    print("")
    print("Continuity Summary:")
    print(" - Current identity: Project L")
    print(" - Current role: Cognitive memory system")
    print(" - Current phase: memory orchestration and continuity")
    print(" - Next layer: Recall Bridge Engine")
    print("")

if __name__ == "__main__":
    run()
