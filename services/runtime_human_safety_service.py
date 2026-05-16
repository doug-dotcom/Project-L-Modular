# =====================================================
# runtime_human_safety_service.py
# AODS 73
# =====================================================

from datetime import datetime

from services.runtime_mission_control_service import (
    mission_summary,
    mission_alerts
)

from services.runtime_confidence_service import (
    runtime_alignment
)

SAFE_STATES = {
    "stable": {
        "summary": "Runtime stable and operating normally.",
        "guidance": "Safe to continue expanding carefully."
    },
    "watch": {
        "summary": "Runtime stable but beginning to drift.",
        "guidance": "Slow pacing recommended. Validate before expanding."
    },
    "unstable": {
        "summary": "Runtime instability detected.",
        "guidance": "Pause expansion and stabilise current systems."
    }
}

def human_runtime_status():

    summary = mission_summary()

    overall = summary.get(
        "overall_state",
        "watch"
    )

    safe = SAFE_STATES.get(
        overall,
        SAFE_STATES["watch"]
    )

    return {
        "timestamp": datetime.now().isoformat(),

        "overall_state": overall,

        "human_summary": safe["summary"],

        "guidance": safe["guidance"],

        "confidence_score": summary.get(
            "confidence_score",
            0
        ),

        "drift_score": summary.get(
            "drift_score",
            0
        ),

        "alignment_score": summary.get(
            "alignment_score",
            0
        )
    }

def reassurance_panel():

    runtime = human_runtime_status()

    alignment = runtime_alignment()

    alignment_score = alignment.get(
        "alignment_score",
        0
    )

    reassurance = (
        "System operating within expected conditions."
        if alignment_score >= 60 else
        "System stable but requires careful pacing."
        if alignment_score >= 40 else
        "System requires stabilisation before expansion."
    )

    return {
        "timestamp": datetime.now().isoformat(),

        "reassurance": reassurance,

        "state": runtime,

        "recommendation": runtime.get(
            "guidance"
        )
    }

def overload_check():

    alerts = mission_alerts()

    alert_count = alerts.get(
        "alert_count",
        0
    )

    overload = (
        "low"
        if alert_count <= 1 else
        "moderate"
        if alert_count <= 3 else
        "high"
    )

    recommendation = (
        "Continue current pace."
        if overload == "low" else
        "Reduce complexity and validate more often."
        if overload == "moderate" else
        "Pause expansion and stabilise runtime."
    )

    return {
        "timestamp": datetime.now().isoformat(),

        "overload_level": overload,

        "alert_count": alert_count,

        "recommendation": recommendation,

        "alerts": alerts.get("alerts", [])
    }

def human_brief():

    return {
        "timestamp": datetime.now().isoformat(),

        "runtime": human_runtime_status(),

        "reassurance": reassurance_panel(),

        "overload": overload_check()
    }
