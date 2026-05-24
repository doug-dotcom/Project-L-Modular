# =====================================================
# runtime_task_queue_service.py
# AODS 65
# =====================================================

import json
import uuid
from pathlib import Path
from datetime import datetime

QUEUE_DIR = Path("queue")
QUEUE_FILE = QUEUE_DIR / "runtime_queue.json"

MAX_QUEUE_ITEMS = 500

def ensure_queue():

    QUEUE_DIR.mkdir(exist_ok=True)

    if not QUEUE_FILE.exists():

        with open(QUEUE_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)

def load_queue():

    ensure_queue()

    try:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

        return []

    except Exception:
        return []

def save_queue(items):

    items = items[-MAX_QUEUE_ITEMS:]

    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)

def enqueue_task(
    captain,
    task_type,
    payload,
    priority="normal",
    thread_id="default"
):

    queue = load_queue()

    task = {
        "task_id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        "captain": captain,
        "task_type": task_type,
        "priority": priority,
        "thread_id": thread_id,
        "payload": payload,
        "status": "queued"
    }

    queue.append(task)

    save_queue(queue)

    return task

def queue_status():

    queue = load_queue()

    queued = [
        q for q in queue
        if q.get("status") == "queued"
    ]

    completed = [
        q for q in queue
        if q.get("status") == "completed"
    ]

    return {
        "queue_size": len(queue),
        "queued_tasks": len(queued),
        "completed_tasks": len(completed),
        "status": "online"
    }

def recent_tasks(limit=20):

    queue = load_queue()

    return queue[-limit:]

def next_queued_task():

    queue = load_queue()

    for task in queue:

        if task.get("status") == "queued":
            return task

    return None

def mark_task_complete(task_id):

    queue = load_queue()

    for task in queue:

        if task.get("task_id") == task_id:

            task["status"] = "completed"
            task["completed_at"] = datetime.now().isoformat()

    save_queue(queue)

    return {
        "task_id": task_id,
        "status": "completed"
    }
