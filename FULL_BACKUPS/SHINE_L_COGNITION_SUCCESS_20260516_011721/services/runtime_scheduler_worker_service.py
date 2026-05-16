# =====================================================
# runtime_scheduler_worker_service.py
# AODS 66
# =====================================================

from services.runtime_scheduler_service import (
    due_tasks,
    mark_schedule_complete
)

from services.runtime_task_queue_service import (
    enqueue_task
)

from services.agent_bus_service import (
    publish_message
)

def process_due_schedules():

    due = due_tasks()

    processed = []

    for item in due:

        enqueue_task(
            captain=item.get("captain", "L"),
            task_type=item.get("task_type", "general"),
            payload=item.get("payload", {}),
            priority=item.get("priority", "normal"),
            thread_id=item.get("thread_id", "default")
        )

        publish_message(
            sender="Scheduler",
            recipient=item.get("captain", "L"),
            message_type="scheduled_task",
            content=str(item),
            priority=item.get("priority", "normal"),
            thread_id=item.get("thread_id", "default")
        )

        mark_schedule_complete(
            item.get("schedule_id")
        )

        processed.append(item)

    return {
        "processed_count": len(processed),
        "processed": processed,
        "status": "complete"
    }
