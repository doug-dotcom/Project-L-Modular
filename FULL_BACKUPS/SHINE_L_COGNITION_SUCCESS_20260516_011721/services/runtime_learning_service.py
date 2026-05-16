# =====================================================
# runtime_learning_service.py
# AODS 76
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

LEARNING_FILE = (
    Path("learning")
    / "runtime_learning_store.json"
)

MAX_PATTERNS = 500

def load_learning_store():

    try:
        with open(
            LEARNING_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except Exception:

        return {
            "successful_patterns": [],
            "failed_patterns": [],
            "adaptation_rules": {}
        }

def save_learning_store(data):

    with open(
        LEARNING_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(data, f, indent=2)

def record_successful_pattern(
    pattern,
    context=None
):

    data = load_learning_store()

    success = data.get(
        "successful_patterns",
        []
    )

    success.append({
        "timestamp": datetime.now().isoformat(),
        "pattern": pattern,
        "context": context or {}
    })

    success = success[-MAX_PATTERNS:]

    data["successful_patterns"] = success

    save_learning_store(data)

    return {
        "status": "recorded",
        "type": "successful_pattern",
        "pattern": pattern
    }

def record_failed_pattern(
    pattern,
    context=None
):

    data = load_learning_store()

    failed = data.get(
        "failed_patterns",
        []
    )

    failed.append({
        "timestamp": datetime.now().isoformat(),
        "pattern": pattern,
        "context": context or {}
    })

    failed = failed[-MAX_PATTERNS:]

    data["failed_patterns"] = failed

    save_learning_store(data)

    return {
        "status": "recorded",
        "type": "failed_pattern",
        "pattern": pattern
    }

def learning_summary():

    data = load_learning_store()

    return {
        "timestamp": datetime.now().isoformat(),

        "successful_patterns": len(
            data.get(
                "successful_patterns",
                []
            )
        ),

        "failed_patterns": len(
            data.get(
                "failed_patterns",
                []
            )
        ),

        "adaptation_rules": data.get(
            "adaptation_rules",
            {}
        ),

        "status": "online"
    }

def adaptive_recommendation():

    alignment = runtime_alignment()

    overload = overload_check()

    data = load_learning_store()

    successful = len(
        data.get(
            "successful_patterns",
            []
        )
    )

    failed = len(
        data.get(
            "failed_patterns",
            []
        )
    )

    alignment_score = alignment.get(
        "alignment_score",
        0
    )

    overload_level = overload.get(
        "overload_level",
        "moderate"
    )

    if failed > successful:

        recommendation = (
            "Reduce expansion pace and validate more carefully."
        )

    elif overload_level == "high":

        recommendation = (
            "Lower runtime complexity before expanding."
        )

    elif alignment_score >= 70:

        recommendation = (
            "Runtime stable for gradual capability expansion."
        )

    else:

        recommendation = (
            "Maintain observation and continue measured pacing."
        )

    return {
        "timestamp": datetime.now().isoformat(),

        "successful_patterns": successful,

        "failed_patterns": failed,

        "recommendation": recommendation
    }

def recent_learning(limit=10):

    data = load_learning_store()

    successful = data.get(
        "successful_patterns",
        []
    )[-limit:]

    failed = data.get(
        "failed_patterns",
        []
    )[-limit:]

    return {
        "successful": successful,
        "failed": failed
    }
