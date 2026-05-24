import json
import os
from datetime import datetime

ROOT_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        ".."
    )
)

# =====================================================
# ROUTING
# =====================================================

def should_handle(message: str) -> bool:

    text = message.lower()

    triggers = [

        "task",
        "todo",
        "to-do",
        "remind me",
        "deadline",
        "follow up",
        "priority",
        "track this",
        "add task"

    ]

    return any(
        t in text
        for t in triggers
    )

# =====================================================
# CLEAN TASK
# =====================================================

def clean_task(message: str):

    text = message.strip()

    remove_words = [

        "task",
        "todo",
        "to-do",
        "track this",
        "remind me",
        "add task"

    ]

    for word in remove_words:

        text = text.replace(word, "")
        text = text.replace(word.title(), "")

    return text.strip()

# =====================================================
# PRIORITY
# =====================================================

def detect_priority(message: str):

    text = message.lower()

    if any(
        word in text
        for word in [
            "urgent",
            "critical",
            "important",
            "asap"
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
# BUILD TASK HANDOFF
# =====================================================

def build_task_handoff(message: str):

    task = clean_task(message)

    priority = detect_priority(message)

    return {

        "timestamp":
            datetime.now().isoformat(),

        "task":
            task,

        "priority":
            priority,

        "source":
            "Addie"

    }

# =====================================================
# MAIN
# =====================================================

def handle_task_request(message: str):

    handoff = build_task_handoff(
        message
    )

    return {

        "status":
            "handoff_ready",

        "handoff":
            handoff

    }
