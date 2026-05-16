# =====================================================
# runtime_task_worker_service.py
# AODS 65
# =====================================================

from services.runtime_task_queue_service import (
    next_queued_task,
    mark_task_complete
)

from services.captain_action_service import ACTION_ENGINE

from services.agent_bus_service import publish_message

def process_next_task():

    task = next_queued_task()

    if not task:

        return {
            "status": "idle",
            "message": "No queued tasks"
        }

    captain = task.get("captain", "L")

    payload = task.get("payload", {})

    result = ACTION_ENGINE.execute(
        captain,
        payload
    )

    mark_task_complete(
        task.get("task_id")
    )

    publish_message(
        sender=captain,
        recipient="Doug",
        message_type="task_complete",
        content=str(result),
        priority=task.get("priority", "normal"),
        thread_id=task.get("thread_id", "default")
    )

    return {
        "processed_task": task,
        "result": result,
        "status": "processed"
    }
