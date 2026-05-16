# =====================================================
# runtime_strategy_service.py
# AODS 71
# =====================================================

import json
import uuid
from pathlib import Path
from datetime import datetime

from services.runtime_governance_service import constitutional_alignment
from services.runtime_expansion_gateway_service import expansion_readiness
from services.runtime_confidence_service import (
    runtime_alignment,
    drift_score,
    confidence_score
)

PLAN_DIR = Path("plans")
PLAN_FILE = PLAN_DIR / "strategic_plans.json"

MAX_PLANS = 1000

def ensure_plan_store():

    PLAN_DIR.mkdir(exist_ok=True)

    if not PLAN_FILE.exists():

        with open(PLAN_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)

def load_plans():

    ensure_plan_store()

    try:
        with open(PLAN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

        return []

    except Exception:
        return []

def save_plans(plans):

    plans = plans[-MAX_PLANS:]

    with open(PLAN_FILE, "w", encoding="utf-8") as f:
        json.dump(plans, f, indent=2)

def strategic_priority():

    alignment = runtime_alignment()
    drift = drift_score()
    confidence = confidence_score()

    alignment_score = alignment.get(
        "alignment_score",
        0
    )

    drift_value = drift.get(
        "drift_score",
        0
    )

    confidence_value = confidence.get(
        "confidence_score",
        0
    )

    if drift_value >= 60:

        return {
            "priority": "stabilise_runtime",
            "reason": "high_drift_detected"
        }

    if confidence_value < 50:

        return {
            "priority": "increase_confidence",
            "reason": "low_confidence_detected"
        }

    governance = constitutional_alignment()

    readiness = expansion_readiness()

    governance_state = governance.get(
        "governance_state"
    )

    if alignment_score >= 70 and governance_state == "constitutional":

        return {
            "priority": "expand_capabilities",
            "reason": "stable_alignment_detected"
        }

    return {
        "priority": "maintain_observation",
        "reason": "normal_runtime_conditions"
    }

def build_plan(
    title,
    objective,
    steps,
    priority="normal"
):

    plans = load_plans()

    plan = {
        "plan_id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "title": title,
        "objective": objective,
        "steps": steps,
        "priority": priority,
        "runtime_priority": strategic_priority(),
        "status": "planned"
    }

    plans.append(plan)

    save_plans(plans)

    return plan

def recent_plans(limit=20):

    plans = load_plans()

    return plans[-limit:]

def planning_status():

    plans = load_plans()

    active = [
        p for p in plans
        if p.get("status") == "planned"
    ]

    return {
        "plan_count": len(plans),
        "active_plans": len(active),
        "status": "online"
    }

def strategic_snapshot():

    return {
        "timestamp": datetime.now().isoformat(),
        "priority": strategic_priority(),
        "alignment": runtime_alignment(),
        "confidence": confidence_score(),
        "drift": drift_score()
    }



