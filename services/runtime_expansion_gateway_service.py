# =====================================================
# runtime_expansion_gateway_service.py
# AODS 75
# =====================================================

import json
from pathlib import Path
from datetime import datetime

from services.runtime_governance_service import (
    constitutional_alignment
)

from services.runtime_confidence_service import (
    confidence_score,
    drift_score
)

from services.runtime_learning_service import adaptive_recommendation
from services.runtime_lock_service import runtime_permitted
from services.runtime_human_safety_service import (
    overload_check
)

GATEWAY_FILE = (
    Path("gateway")
    / "expansion_policy.json"
)

def load_policy():

    try:
        with open(
            GATEWAY_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except Exception:

        return {}

def expansion_policy():

    policy = load_policy()

    return policy.get(
        "expansion_rules",
        {}
    )

def expansion_types():

    policy = load_policy()

    return policy.get(
        "expansion_types",
        {}
    )

def expansion_readiness():

    rules = expansion_policy()

    governance = constitutional_alignment()

    confidence = confidence_score()

    drift = drift_score()

    overload = overload_check()

    alignment_score = governance.get(
        "alignment_score",
        0
    )

    governance_state = governance.get(
        "governance_state",
        "watch"
    )

    confidence_value = confidence.get(
        "confidence_score",
        0
    )

    drift_value = drift.get(
        "drift_score",
        100
    )

    overload_level = overload.get(
        "overload_level",
        "high"
    )

    ready = (
        alignment_score >= rules.get(
            "minimum_alignment_score",
            60
        )

        and confidence_value >= rules.get(
            "required_confidence_score",
            60
        )

        and drift_value <= rules.get(
            "maximum_drift_score",
            40
        )

        and governance_state == rules.get(
            "required_governance_state",
            "constitutional"
        )

        and overload_level != "high"
    )

    learning = adaptive_recommendation()

    return {
        "timestamp": datetime.now().isoformat(),

        "learning_recommendation": learning,

        "expansion_ready": ready,

        "alignment_score": alignment_score,

        "confidence_score": confidence_value,

        "drift_score": drift_value,

        "governance_state": governance_state,

        "overload_level": overload_level
    }

def expansion_gate(expansion_type):

    readiness = expansion_readiness()

    types = expansion_types()

    expansion = types.get(
        expansion_type,
        {
            "risk": "unknown",
            "approval": "manual_review"
        }
    )

    ready = readiness.get(
        "expansion_ready",
        False
    )

    approval = expansion.get(
        "approval",
        "manual_review"
    )

    permitted = (
        ready
        and approval != "manual_review"
    )

    return {
        "timestamp": datetime.now().isoformat(),

        "expansion_type": expansion_type,

        "risk": expansion.get("risk"),

        "approval_mode": approval,

        "expansion_ready": ready,

        "permitted": permitted,

        "readiness": readiness
    }

def expansion_brief():

    return {
        "timestamp": datetime.now().isoformat(),

        "policy": expansion_policy(),

        "types": expansion_types(),

        "readiness": expansion_readiness()
    }



