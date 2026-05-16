# =====================================================
# runtime_lock_service.py
# AODS 82
# =====================================================

import json
from pathlib import Path
from datetime import datetime

from services.runtime_confidence_service import (
    drift_score,
    runtime_alignment
)

from services.runtime_human_safety_service import (
    overload_check
)

LOCK_FILE = (
    Path("locks")
    / "runtime_lock_state.json"
)

def load_lock_state():

    try:
        with open(
            LOCK_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except Exception:

        return {
            "lock_status": {},
            "lock_rules": {}
        }

def save_lock_state(data):

    with open(
        LOCK_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(data, f, indent=2)

def runtime_lock_status():

    data = load_lock_state()

    return data.get(
        "lock_status",
        {}
    )

def runtime_lock_rules():

    data = load_lock_state()

    return data.get(
        "lock_rules",
        {}
    )

def evaluate_lock_conditions():

    rules = runtime_lock_rules()

    drift = drift_score()

    alignment = runtime_alignment()

    overload = overload_check()

    drift_value = drift.get(
        "drift_score",
        0
    )

    alignment_score = alignment.get(
        "alignment_score",
        100
    )

    overload_level = overload.get(
        "overload_level",
        "low"
    )

    locked = False
    reason = ""

    if drift_value >= rules.get(
        "critical_drift_threshold",
        75
    ):

        locked = True
        reason = "critical_drift_detected"

    elif alignment_score <= rules.get(
        "minimum_alignment_threshold",
        35
    ):

        locked = True
        reason = "low_alignment_detected"

    elif (
        rules.get(
            "high_overload_locks_runtime",
            True
        )
        and overload_level == "high"
    ):

        locked = True
        reason = "high_overload_detected"

    return {
        "timestamp": datetime.now().isoformat(),

        "runtime_locked": locked,

        "reason": reason,

        "drift_score": drift_value,

        "alignment_score": alignment_score,

        "overload_level": overload_level
    }

def apply_runtime_lock():

    data = load_lock_state()

    status = evaluate_lock_conditions()

    data["lock_status"] = status

    save_lock_state(data)

    return status

def lock_brief():

    return {
        "timestamp": datetime.now().isoformat(),

        "status": runtime_lock_status(),

        "rules": runtime_lock_rules(),

        "evaluation": evaluate_lock_conditions()
    }

def runtime_permitted():

    status = evaluate_lock_conditions()

    return {
        "timestamp": datetime.now().isoformat(),

        "runtime_permitted": (
            not status.get(
                "runtime_locked",
                False
            )
        ),

        "status": status
    }
