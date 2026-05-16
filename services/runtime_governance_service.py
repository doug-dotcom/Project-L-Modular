# =====================================================
# runtime_governance_service.py
# AODS 74
# =====================================================

import json
from pathlib import Path
from datetime import datetime

from services.runtime_confidence_service import (
    runtime_alignment
)

from services.runtime_human_safety_service import (
    overload_check
)

GOVERNANCE_FILE = (
    Path("governance")
    / "runtime_constitution.json"
)

def load_constitution():

    try:
        with open(
            GOVERNANCE_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except Exception:

        return {
            "constitutional_doctrine": {}
        }

def constitutional_doctrine():

    constitution = load_constitution()

    return constitution.get(
        "constitutional_doctrine",
        {}
    )

def governance_status():

    doctrine = constitutional_doctrine()

    return {
        "timestamp": datetime.now().isoformat(),

        "core_principles": doctrine.get(
            "core_principles",
            []
        ),

        "runtime_restrictions": doctrine.get(
            "runtime_restrictions",
            []
        ),

        "safety_requirements": doctrine.get(
            "safety_requirements",
            []
        ),

        "status": "active"
    }

def constitutional_alignment():

    alignment = runtime_alignment()

    overload = overload_check()

    alignment_score = alignment.get(
        "alignment_score",
        0
    )

    overload_level = overload.get(
        "overload_level",
        "moderate"
    )

    governance_state = (
        "constitutional"
        if alignment_score >= 70
        and overload_level == "low"

        else "watch"

        if alignment_score >= 40

        else "unstable"
    )

    return {
        "timestamp": datetime.now().isoformat(),

        "alignment_score": alignment_score,

        "overload_level": overload_level,

        "governance_state": governance_state
    }

def governance_recommendation():

    state = constitutional_alignment()

    governance_state = state.get(
        "governance_state"
    )

    if governance_state == "constitutional":

        recommendation = (
            "Runtime operating within constitutional doctrine."
        )

    elif governance_state == "watch":

        recommendation = (
            "Slow expansion and validate carefully."
        )

    else:

        recommendation = (
            "Pause expansion and stabilise runtime."
        )

    return {
        "timestamp": datetime.now().isoformat(),

        "governance_state": governance_state,

        "recommendation": recommendation
    }

def governance_brief():

    return {
        "timestamp": datetime.now().isoformat(),

        "constitution": governance_status(),

        "alignment": constitutional_alignment(),

        "recommendation": governance_recommendation()
    }
