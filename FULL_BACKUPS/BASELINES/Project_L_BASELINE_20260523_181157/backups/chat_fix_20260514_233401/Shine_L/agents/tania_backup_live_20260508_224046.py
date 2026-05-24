import json
import os
from datetime import datetime

TASK_PATH = "C:/Shine_L/memory/tasks.json"


def load_tasks():
    try:
        with open(TASK_PATH, "r") as f:
            return json.load(f)
    except:
        return []


def save_tasks(tasks):
    with open(TASK_PATH, "w") as f:
        json.dump(tasks, f, indent=2)


def create_task(text):
    tasks = load_tasks()

    task = {
        "task": text,
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }

    tasks.append(task)
    save_tasks(tasks)

    return f"Got it. I've added '{text}' as a task."


def list_tasks():
    tasks = load_tasks()

    if not tasks:
        return "You have no tasks right now."

    response = "Here’s what we’ve got:\n\n"

    for i, t in enumerate(tasks, 1):
        if t["status"] == "pending":
            response += f"{i}. {t['task']}\n"

    return response