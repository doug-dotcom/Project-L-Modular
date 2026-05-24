# =====================================================
# runtime_executive_service.py
# AODS 80
# =====================================================

from datetime import datetime

from services.runtime_intent_service import intent_summary
from services.runtime_mission_control_service import mission_summary, mission_alerts
from services.runtime_strategy_service import strategic_priority
from services.runtime_expansion_gateway_service import expansion_readiness
from services.runtime_task_queue_service import enqueue_task
from services.agent_bus_service import publish_message

def executive_assess(user_message, thread_id="default"):

    intent = intent_summary(user_message)
    mission = mission_summary()
    alerts = mission_alerts()
    strategy = strategic_priority()
    expansion = expansion_readiness()

    dominant = intent.get("dominant_intent", {}).get("intent", "general")

    if mission.get("overall_state") == "unstable":
        decision = "stabilise_before_action"
        captain = "Captain Builder"
        priority = "high"

    elif alerts.get("alert_count", 0) >= 3:
        decision = "reduce_complexity"
        captain = "Major Tegan Triage"
        priority = "high"

    elif dominant == "build":
        decision = "route_build"
        captain = "Captain Builder"
        priority = "high"

    elif dominant == "memory":
        decision = "route_memory"
        captain = "Captain Memory"
        priority = "normal"

    elif dominant == "care":
        decision = "route_care"
        captain = "Captain Emme"
        priority = "high"

    elif dominant == "strategy":
        decision = "route_strategy"
        captain = "L"
        priority = "normal"

    else:
        decision = "route_general"
        captain = "L"
        priority = "normal"

    return {
        "timestamp": datetime.now().isoformat(),
        "input": user_message,
        "dominant_intent": dominant,
        "decision": decision,
        "assigned_to": captain,
        "priority": priority,
        "mission": mission,
        "alerts": alerts,
        "strategy": strategy,
        "expansion": expansion
    }

def executive_dispatch(user_message, thread_id="default"):

    assessment = executive_assess(user_message, thread_id)

    task = enqueue_task(
        captain=assessment.get("assigned_to", "L"),
        task_type=assessment.get("decision", "general"),
        payload={
            "message": user_message,
            "executive_assessment": assessment
        },
        priority=assessment.get("priority", "normal"),
        thread_id=thread_id
    )

    publish_message(
        sender="Executive Coordination",
        recipient=assessment.get("assigned_to", "L"),
        message_type="executive_dispatch",
        content=str(assessment),
        priority=assessment.get("priority", "normal"),
        thread_id=thread_id
    )

    return {
        "assessment": assessment,
        "queued_task": task,
        "status": "dispatched"
    }

def executive_status():

    return {
        "timestamp": datetime.now().isoformat(),
        "service": "Runtime Executive Coordination",
        "status": "online",
        "role": "Coordinates intent, mission state, strategy, gateway readiness, and task routing."
    }
