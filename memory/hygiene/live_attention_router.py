import json
import re
from pathlib import Path
from datetime import datetime

ROOT = Path(r"C:\Shine_L")

INJECTION_FILE = ROOT / "memory" / "injection" / "runtime_memory_injection.json"
CONVO_FILE = ROOT / "memory" / "conversation" / "conversational_state.json"
STATE_FILE = ROOT / "memory" / "state" / "cognitive_states.json"
ATTENTION_FILE = ROOT / "memory" / "attention" / "attention_orchestration.json"

OUT_DIR = ROOT / "memory" / "router"
REPORT_DIR = ROOT / "memory" / "hygiene" / "reports"

ROUTES = {
    "project_l_route": ["project l", "aods", "engine", "runtime", "memory", "server", "architecture"],
    "recovery_route": ["recovery", "meeting", "step", "regulation", "addiction", "hps"],
    "identity_route": ["identity", "mask", "doug", "dougie", "douglas", "self worth", "who i am"],
    "family_route": ["family", "kids", "iyla", "ashton", "luella", "mehlia", "father"],
    "stress_route": ["fear", "money", "stress", "unsafe", "panic", "pressure"]
}

def load_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def route_text(text):
    text = re.sub(r"\s+", " ", str(text or "")).lower().strip()
    scores = {}

    for route, patterns in ROUTES.items():
        score = 0
        for p in patterns:
            if p in text:
                score += 1
        scores[route] = score

    best_route = max(scores, key=scores.get) if scores else "general_route"

    if scores.get(best_route, 0) == 0:
        best_route = "general_route"

    return best_route, scores

def run():

    print("")
    print("Loading attention routing layers...")

    injection = load_json(INJECTION_FILE)
    convo = load_json(CONVO_FILE)
    state = load_json(STATE_FILE)
    attention = load_json(ATTENTION_FILE)

    sample_inputs = [
        "continue Project L AODS runtime memory work",
        "I feel stressed and unsafe about money",
        "talk about identity and masks",
        "family and kids matter",
        "recovery meeting regulation"
    ]

    route_tests = []

    for s in sample_inputs:
        route, scores = route_text(s)
        route_tests.append({
            "sample": s,
            "selected_route": route,
            "scores": scores
        })

    router = {
        "created_at": str(datetime.utcnow()),
        "router_name": "Live Attention Router",
        "purpose": "Route live input toward the most relevant cognition and memory pathway.",
        "available_routes": list(ROUTES.keys()) + ["general_route"],
        "routing_rules": ROUTES,
        "default_route": "general_route",
        "route_tests": route_tests,
        "runtime_behavior": [
            "classify incoming user text",
            "select strongest attention route",
            "activate matching memory layer",
            "preserve continuity if route is unclear",
            "fall back to general context safely"
        ],
        "next_evolutionary_goal": "Context Window Compression Engine"
    }

    out_path = OUT_DIR / "live_attention_router.json"

    out_path.write_text(
        json.dumps(router, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    report_path = REPORT_DIR / f"live_attention_router_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"

    report_path.write_text(
        json.dumps(router, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print("")
    print("Live attention router complete.")
    print(f"Router written to: {out_path}")
    print(f"Report written to: {report_path}")
    print("")
    print("Router Summary:")
    print(" - Project L route online")
    print(" - Recovery route online")
    print(" - Identity route online")
    print(" - Family route online")
    print(" - Stress route online")
    print(" - General fallback online")
    print("")

if __name__ == "__main__":
    run()
