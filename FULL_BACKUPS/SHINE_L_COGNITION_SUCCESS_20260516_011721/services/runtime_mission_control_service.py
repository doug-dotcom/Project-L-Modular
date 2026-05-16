# =====================================================
# runtime_mission_control_service.py
# AODS 72
# =====================================================

from datetime import datetime

from services.runtime_state_service import runtime_status
from services.runtime_confidence_service import (
    confidence_score,
    drift_score,
    runtime_alignment
)
from services.runtime_strategy_service import (
    strategic_priority,
    strategic_snapshot
)
from services.runtime_task_queue_service import (
    queue_status
)
from services.runtime_scheduler_service import (
    scheduler_status
)
from services.runtime_audit_service import (
    ledger_status
)
from services.runtime_knowledge_graph_service import (
    graph_status
)
from services.runtime_replay_service import (
    replay_status
)
from services.guardian_service import (
    guardian_status
)

def mission_snapshot():

    return {
        "timestamp": datetime.now().isoformat(),

        "runtime": runtime_status(),

        "confidence": confidence_score(),

        "drift": drift_score(),

        "alignment": runtime_alignment(),

        "strategy": strategic_priority(),

        "queue": queue_status(),

        "scheduler": scheduler_status(),

        "audit": ledger_status(),

        "graph": graph_status(),

        "replay": replay_status(),

        "guardian": guardian_status()
    }

def mission_summary():

    snapshot = mission_snapshot()

    confidence = snapshot["confidence"]
    drift = snapshot["drift"]
    alignment = snapshot["alignment"]

    return {
        "timestamp": datetime.now().isoformat(),

        "runtime_status": snapshot["runtime"].get(
            "runtime_status",
            "UNKNOWN"
        ),

        "confidence_score": confidence.get(
            "confidence_score",
            0
        ),

        "drift_score": drift.get(
            "drift_score",
            0
        ),

        "alignment_score": alignment.get(
            "alignment_score",
            0
        ),

        "strategic_priority": snapshot["strategy"],

        "queue_status": snapshot["queue"],

        "scheduler_status": snapshot["scheduler"],

        "guardian_status": snapshot["guardian"],

        "overall_state": (
            "stable"
            if alignment.get("alignment_score", 0) >= 60
            else "watch"
            if alignment.get("alignment_score", 0) >= 40
            else "unstable"
        )
    }

def mission_alerts():

    snapshot = mission_snapshot()

    alerts = []

    if snapshot["drift"].get("drift_score", 0) >= 50:

        alerts.append({
            "severity": "high",
            "type": "drift",
            "message": "Elevated runtime drift detected"
        })

    if snapshot["confidence"].get("confidence_score", 0) < 50:

        alerts.append({
            "severity": "medium",
            "type": "confidence",
            "message": "Low runtime confidence detected"
        })

    if snapshot["queue"].get("queued_tasks", 0) > 25:

        alerts.append({
            "severity": "medium",
            "type": "queue",
            "message": "Queue backlog increasing"
        })

    if snapshot["scheduler"].get("due_tasks", 0) > 10:

        alerts.append({
            "severity": "medium",
            "type": "scheduler",
            "message": "Large number of due scheduled tasks"
        })

    return {
        "timestamp": datetime.now().isoformat(),
        "alert_count": len(alerts),
        "alerts": alerts
    }

def command_brief():

    summary = mission_summary()

    alerts = mission_alerts()

    return {
        "timestamp": datetime.now().isoformat(),
        "summary": summary,
        "alerts": alerts,
        "strategic_snapshot": strategic_snapshot()
    }

def mission_human_state():

    summary = mission_summary()

    return {
        "overall_state": summary.get("overall_state"),
        "confidence_score": summary.get("confidence_score"),
        "drift_score": summary.get("drift_score"),
        "alignment_score": summary.get("alignment_score")
    }
