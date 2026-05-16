import os
import json
from datetime import datetime

ROOT_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        ".."
    )
)

TASK_FILE = os.path.join(
    ROOT_DIR,
    "memory",
    "addie_tasks.json"
)

os.makedirs(
    os.path.dirname(TASK_FILE),
    exist_ok=True
)

# =====================================================
# LOAD / SAVE
# =====================================================

def _load():

    try:

        if not os.path.exists(TASK_FILE):

            return []

        with open(
            TASK_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if isinstance(data, list):

            return data

        return []

    except Exception as e:

        print("ADDIE LOAD ERROR:", e)

        return []


def _save(data):

    try:

        with open(
            TASK_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                indent=2,
                ensure_ascii=False
            )

    except Exception as e:

        print("ADDIE SAVE ERROR:", e)

# =====================================================
# ROUTING DETECTION
# =====================================================

def should_handle(message: str) -> bool:

    text = message.lower()

    triggers = [

        "addie",
        "task",
        "todo",
        "to-do",
        "remind me",
        "deadline",
        "follow up",
        "priority",
        "important task",
        "track this",
        "add this task"

    ]

    return any(
        phrase in text
        for phrase in triggers
    )

# =====================================================
# CLEAN TASK
# =====================================================

def clean_task(message: str):

    text = message.strip()

    remove_words = [

        "addie",
        "task",
        "add this task",
        "track this",
        "remind me"

    ]

    for word in remove_words:

        text = text.replace(word, "")
        text = text.replace(word.title(), "")

    return text.strip()

# =====================================================
# PRIORITY DETECTION
# =====================================================

def detect_priority(message: str):

    text = message.lower()

    if any(
        word in text
        for word in [
            "urgent",
            "asap",
            "important",
            "critical"
        ]
    ):
        return "high"

    if any(
        word in text
        for word in [
            "later",
            "eventually",
            "sometime"
        ]
    ):
        return "low"

    return "normal"

# =====================================================
# ADD TASK
# =====================================================

def add_task(message: str):

    tasks = _load()

    clean = clean_task(message)

    priority = detect_priority(message)

    entry = {

        "timestamp":
            datetime.now().isoformat(),

        "task":
            clean,

        "priority":
            priority,

        "status":
            "open"

    }

    tasks.append(entry)

    _save(tasks)

    return entry

# =====================================================
# LIST TASKS
# =====================================================

def list_tasks():

    tasks = _load()

    open_tasks = [

        t for t in tasks
        if t.get("status") == "open"

    ]

    if not open_tasks:

        return (
            "# ✅ Addie Task Execution\n\n"
            "No active tasks currently."
        )

    reply = "# ✅ Addie Task Execution\n\n"

    reply += "Current active tasks:\n\n"

    for i, task in enumerate(open_tasks, start=1):

        reply += (
            f"{i}. "
            + task.get("task", "")
            + f" ({task.get('priority','normal')})\n"
        )

    return reply

# =====================================================
# MAIN HANDLER
# =====================================================

def handle_task_request(message: str):

    text = message.lower()

    if (
        "show tasks" in text
        or "list tasks" in text
        or "what are my tasks" in text
    ):

        return list_tasks()

    entry = add_task(message)

    return (
        "# ✅ Addie Task Execution\n\n"
        "Task added successfully.\n\n"
        "Task:\n"
        + entry.get("task","")
        + "\n\nPriority: "
        + entry.get("priority","normal")
    )
