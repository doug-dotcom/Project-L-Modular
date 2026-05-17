# =====================================================
# runtime_scheduler_service.py
# AODS 66
# =====================================================

import json
import uuid
from pathlib import Path
from datetime import datetime, timedelta

SCHEDULE_DIR = Path("schedule")
SCHEDULE_FILE = SCHEDULE_DIR / "runtime_schedule.json"

MAX_SCHEDULES = 500

def ensure_schedule():

    SCHEDULE_DIR.mkdir(exist_ok=True)

    if not SCHEDULE_FILE.exists():

        with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)

def load_schedule():

    ensure_schedule()

    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

        return []

    except Exception:
        return []

def save_schedule(items):

    items = items[-MAX_SCHEDULES:]

    with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)

def schedule_task(
    captain,
    task_type,
    payload,
    run_at,
    recurrence="once",
    priority="normal",
    thread_id="default"
):

    schedules = load_schedule()

    item = {
        "schedule_id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "captain": captain,
        "task_type": task_type,
        "payload": payload,
        "priority": priority,
        "thread_id": thread_id,
        "run_at": run_at,
        "recurrence": recurrence,
        "status": "scheduled"
    }

    schedules.append(item)

    save_schedule(schedules)

    return item

def due_tasks():

    schedules = load_schedule()

    now = datetime.now()

    due = []

    for item in schedules:

        if item.get("status") != "scheduled":
            continue

        try:
            run_time = datetime.fromisoformat(
                item.get("run_at")
            )

            if run_time <= now:
                due.append(item)

        except Exception:
            continue

    return due

def mark_schedule_complete(schedule_id):

    schedules = load_schedule()

    for item in schedules:

        if item.get("schedule_id") == schedule_id:

            recurrence = item.get("recurrence", "once")

            if recurrence == "once":

                item["status"] = "completed"

            elif recurrence == "daily":

                next_run = datetime.fromisoformat(
                    item["run_at"]
                ) + timedelta(days=1)

                item["run_at"] = next_run.isoformat()

            elif recurrence == "hourly":

                next_run = datetime.fromisoformat(
                    item["run_at"]
                ) + timedelta(hours=1)

                item["run_at"] = next_run.isoformat()

    save_schedule(schedules)

def scheduler_status():

    schedules = load_schedule()

    active = [
        s for s in schedules
        if s.get("status") == "scheduled"
    ]

    return {
        "schedule_count": len(schedules),
        "active_schedules": len(active),
        "due_tasks": len(due_tasks()),
        "status": "online"
    }

def recent_schedules(limit=20):

    schedules = load_schedule()

    return schedules[-limit:]
