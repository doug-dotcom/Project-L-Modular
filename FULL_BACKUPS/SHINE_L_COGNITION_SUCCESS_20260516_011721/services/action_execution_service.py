# =====================================================
# action_execution_service.py
# AODS 57
# =====================================================

from services.agent_dispatch_service import dispatch_user_message
from services.captain_action_service import ACTION_ENGINE
from services.workflow_chain_service import execute_chain
from services.agent_bus_service import publish_message
from services.runtime_task_queue_service import enqueue_task

def execute_user_request(user_message, thread_id="default"):

    dispatch = dispatch_user_message(
        user_message,
        thread_id
    )

    triage = dispatch.get("triage", {})

    assigned_to = triage.get(
        "assigned_to",
        "L"
    )

    workflow_result = execute_chain(
        triage.get("category", "general"),
        {
            "message": user_message,
            "thread_id": thread_id
        }
    )

    action_result = ACTION_ENGINE.execute(
        assigned_to,
        {
            "message": user_message,
            "thread_id": thread_id,
            "triage": triage,
            "workflow": workflow_result
        }
    )

    enqueue_task(
        captain=assigned_to,
        task_type=triage.get("category", "general"),
        payload={
            "message": user_message,
            "thread_id": thread_id,
            "triage": triage
        },
        priority=triage.get("priority", "normal"),
        thread_id=thread_id
    )

    publish_message(
        sender=assigned_to,
        recipient="Doug",
        message_type="action_result",
        content=str(action_result),
        priority=triage.get("priority", "normal"),
        thread_id=thread_id
    )

    return {
        "dispatch": dispatch,
        "action_execution": action_result
    }


