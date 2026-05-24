# =====================================================
# TANIA TASK AGENT
# =====================================================

def should_handle(message: str) -> bool:

    text = message.lower()

    triggers = [

        "task",
        "tasks",
        "todo",
        "to-do",
        "reminder",
        "checklist",
        "things to do",
        "add a task",
        "tania"

    ]

    return any(
        t in text
        for t in triggers
    )

# =====================================================
# PLACEHOLDER RESPONSE
# =====================================================

def handle_task_request(message: str):

    return """

# ✅ Tania Tasks

## 🧠 Task Assistant Active

I am Tania, your task and execution specialist.

---

## 🔥 Current Status

Task orchestration is connected successfully.

Live task persistence already exists and will be connected next.

---

## 👀 What I Will Eventually Handle

- to-do lists
- reminders
- priorities
- execution support
- recurring tasks
- action tracking

---

## ✅ Current Phase

Stage 1:
Orchestration and routing.

Stage 2:
Live task execution and persistence.

"""
