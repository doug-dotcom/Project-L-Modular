from datetime import datetime, timedelta

from services.runtime_scheduler_service import (
    schedule_task,
    scheduler_status,
    recent_schedules
)

from services.runtime_scheduler_worker_service import (
    process_due_schedules
)

print("")
print("===================================")
print("AODS 66 VALIDATION")
print("===================================")
print("")

print("INITIAL STATUS:")
print(scheduler_status())

print("")

run_time = (
    datetime.now() - timedelta(seconds=1)
).isoformat()

print("CREATE SCHEDULE:")

schedule_task(
    captain="Captain Builder",
    task_type="build",
    payload={
        "message": "scheduled validation task"
    },
    run_at=run_time,
    recurrence="once",
    priority="high",
    thread_id="aods66"
)

print(scheduler_status())

print("")
print("RECENT SCHEDULES:")
print(recent_schedules())

print("")
print("PROCESS DUE TASKS:")
print(process_due_schedules())

print("")
print("FINAL STATUS:")
print(scheduler_status())
