# =====================================================
# runtime_operator_interface_service.py
# AODS 88
# =====================================================

from datetime import datetime

from services.runtime_mission_control_service import (
    mission_summary,
    mission_alerts
)

from services.runtime_continuity_service import (
    continuity_summary
)

from services.runtime_lock_service import (
    runtime_lock_status
)

from services.runtime_deployment_readiness_service import (
    deployment_recommendation
)

from services.runtime_human_safety_service import (
    reassurance_panel
)

def operator_dashboard():

    mission = mission_summary()

    continuity = continuity_summary()

    lock_status = runtime_lock_status()

    deployment = deployment_recommendation()

    reassurance = reassurance_panel()

    return {
        "timestamp": datetime.now().isoformat(),

        "runtime_state": mission.get(
            "overall_state"
        ),

        "alignment_score": mission.get(
            "alignment_score"
        ),

        "confidence_score": mission.get(
            "confidence_score"
        ),

        "drift_score": mission.get(
            "drift_score"
        ),

        "continuity_valid": continuity.get(
            "continuity_valid"
        ),

        "runtime_locked": lock_status.get(
            "runtime_locked"
        ),

        "deployment_ready": deployment.get(
            "ready_for_deployment"
        ),

        "reassurance": reassurance.get(
            "reassurance"
        )
    }

def operator_alerts():

    alerts = mission_alerts()

    return {
        "timestamp": datetime.now().isoformat(),

        "alert_count": alerts.get(
            "alert_count",
            0
        ),

        "alerts": alerts.get(
            "alerts",
            []
        )
    }

def operator_actions():

    dashboard = operator_dashboard()

    actions = []

    if dashboard.get("runtime_locked"):

        actions.append(
            "Stabilise runtime before expansion."
        )

    if dashboard.get("drift_score", 0) > 40:

        actions.append(
            "Reduce drift before deployment."
        )

    if not dashboard.get("deployment_ready"):

        actions.append(
            "Validate deployment readiness."
        )

    if not actions:

        actions.append(
            "Runtime operating within expected conditions."
        )

    return {
        "timestamp": datetime.now().isoformat(),

        "recommended_actions": actions
    }

def operator_brief():

    return {
        "timestamp": datetime.now().isoformat(),

        "dashboard": operator_dashboard(),

        "alerts": operator_alerts(),

        "actions": operator_actions()
    }
