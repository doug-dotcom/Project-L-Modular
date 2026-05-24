from services.runtime_task_queue_service import (
    enqueue_task,
    queue_status,
    recent_tasks
)

from services.runtime_task_worker_service import (
    process_next_task
)

print("")
print("===================================")
print("AODS 65 VALIDATION")
print("===================================")
print("")

print("INITIAL QUEUE STATUS:")
print(queue_status())

print("")
print("ENQUEUE TASKS:")

enqueue_task(
    captain="Captain Builder",
    task_type="build",
    payload={
        "message": "AODS validation build task"
    },
    priority="high",
    thread_id="aods65"
)

enqueue_task(
    captain="Captain Memory",
    task_type="memory",
    payload={
        "message": "remember this validation"
    },
    priority="normal",
    thread_id="aods65"
)

print(queue_status())

print("")
print("RECENT TASKS:")
print(recent_tasks())

print("")
print("PROCESS TASK:")
print(process_next_task())

print("")
print("FINAL QUEUE STATUS:")
print(queue_status())
