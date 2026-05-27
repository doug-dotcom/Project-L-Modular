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
    "google_tasks.json"
)

os.makedirs(
    os.path.dirname(TASK_FILE),
    exist_ok=True
)

# =====================================================
# SAVE TASK
# =====================================================

def save_google_task(task_data):

    tasks = []

    if os.path.exists(TASK_FILE):

        try:

            with open(
                TASK_FILE,
                "r",
                encoding="utf-8"
            ) as f:

                tasks = json.load(f)

        except:

            tasks = []

    tasks.append(task_data)

    with open(
        TASK_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            tasks,
            f,
            indent=2,
            ensure_ascii=False
        )

# =====================================================
# EXECUTION LAYER
# =====================================================

def create_task_from_handoff(handoff):

    try:

        task_entry = {

            "timestamp":
                datetime.now().isoformat(),

            "task":
                handoff.get("task",""),

            "priority":
                handoff.get("priority","normal"),

            "source":
                "Tania",

            "provider":
                "Google Tasks (Simulated)",

            "status":
                "created"

        }

        save_google_task(
            task_entry
        )

        return {

            "success": True,

            "task":
                task_entry

        }

    except Exception as e:

        print(
            "TANIA EXECUTION ERROR:",
            e
        )

        return {

            "success": False,

            "error": str(e)

        }

# =====================================================
# ROUTING
# =====================================================

def should_handle(message: str) -> bool:

    return False

# =====================================================
# PLACEHOLDER
# =====================================================

def handle_task_request(message: str):

    return """

# ✅ Tania

Execution layer online.

"""
