# =====================================================
# runtime_confidence_service.py
# AODS 70
# =====================================================

from datetime import datetime

from services.runtime_audit_service import recent_events
from services.agent_bus_service import recent_messages
from services.runtime_replay_service import replay_summary
from services.runtime_state_service import runtime_status

MAX_SCORE = 100
MIN_SCORE = 0

def clamp(value):

    return max(
        MIN_SCORE,
        min(MAX_SCORE, int(value))
    )

def confidence_score():

    audit_events = recent_events(25)
    bus_messages = recent_messages(25)
    replay = replay_summary(25)

    score = 50

    # -------------------------------------------------
    # SIGNAL DENSITY
    # -------------------------------------------------

    if len(audit_events) > 10:
        score += 15

    if len(bus_messages) > 10:
        score += 10

    # -------------------------------------------------
    # REPLAY QUALITY
    # -------------------------------------------------

    if replay.get("event_count", 0) > 10:
        score += 10

    # -------------------------------------------------
    # RUNTIME HEALTH
    # -------------------------------------------------

    runtime = runtime_status()

    if runtime.get("runtime_status") == "ONLINE":
        score += 10

    # -------------------------------------------------
    # ACTIVE AGENTS
    # -------------------------------------------------

    active_agents = runtime.get(
        "active_agents",
        []
    )

    if len(active_agents) >= 3:
        score += 5

    return {
        "timestamp": datetime.now().isoformat(),
        "confidence_score": clamp(score),
        "status": (
            "stable"
            if score >= 75 else
            "moderate"
            if score >= 50 else
            "low"
        )
    }

def drift_score():

    audit_events = recent_events(50)

    drift = 0

    # -------------------------------------------------
    # DETECT ERROR EVENTS
    # -------------------------------------------------

    for event in audit_events:

        payload = str(
            event.get("payload", "")
        ).lower()

        if "error" in payload:
            drift += 10

        if "failed" in payload:
            drift += 10

        if "missing" in payload:
            drift += 5

    # -------------------------------------------------
    # DETECT RUNTIME NOISE
    # -------------------------------------------------

    if len(audit_events) > 40:
        drift += 10

    drift = clamp(drift)

    return {
        "timestamp": datetime.now().isoformat(),
        "drift_score": drift,
        "status": (
            "critical"
            if drift >= 75 else
            "elevated"
            if drift >= 40 else
            "stable"
        )
    }

def runtime_alignment():

    confidence = confidence_score()
    drift = drift_score()

    confidence_value = confidence["confidence_score"]
    drift_value = drift["drift_score"]

    alignment = clamp(
        confidence_value - drift_value
    )

    return {
        "timestamp": datetime.now().isoformat(),
        "confidence": confidence,
        "drift": drift,
        "alignment_score": alignment,
        "runtime_state": (
            "aligned"
            if alignment >= 60 else
            "watch"
            if alignment >= 40 else
            "unstable"
        )
    }

def drift_signals():

    audit_events = recent_events(50)

    signals = []

    for event in audit_events:

        payload = str(
            event.get("payload", "")
        ).lower()

        if "error" in payload:

            signals.append({
                "type": "error_signal",
                "event": event
            })

        if "failed" in payload:

            signals.append({
                "type": "failure_signal",
                "event": event
            })

        if "missing" in payload:

            signals.append({
                "type": "missing_signal",
                "event": event
            })

    return {
        "timestamp": datetime.now().isoformat(),
        "signal_count": len(signals),
        "signals": signals[-20:]
    }
