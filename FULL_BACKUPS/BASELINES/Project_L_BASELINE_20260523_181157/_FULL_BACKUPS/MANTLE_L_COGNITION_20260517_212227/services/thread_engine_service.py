# =====================================================
# thread_engine_service.py
# AODS 55
# =====================================================

import json
from pathlib import Path
from datetime import datetime
from services.runtime_state_service import increment_threads

THREAD_DIR = Path("threads")

MAX_THREAD_MESSAGES = 20

def ensure_thread_dir():
    THREAD_DIR.mkdir(exist_ok=True)

def thread_path(thread_id):

    ensure_thread_dir()

    safe_id = str(thread_id).replace("/", "_")

    return THREAD_DIR / f"{safe_id}.json"

def load_thread(thread_id):

    path = thread_path(thread_id)

    if not path.exists():
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_thread(thread_id, messages):

    path = thread_path(thread_id)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(messages, f, indent=2)

def append_thread(thread_id, role, content):

    increment_threads()

    messages = load_thread(thread_id)

    messages.append({
        "timestamp": datetime.now().isoformat(),
        "role": role,
        "content": content
    })

    messages = messages[-MAX_THREAD_MESSAGES:]

    save_thread(thread_id, messages)

    return messages

def thread_context(thread_id):

    messages = load_thread(thread_id)

    formatted = []

    for m in messages:

        role = m.get("role", "unknown")
        content = m.get("content", "")

        formatted.append(f"{role}: {content}")

    return "\n".join(formatted)

def thread_status(thread_id):

    messages = load_thread(thread_id)

    return {
        "thread_id": thread_id,
        "message_count": len(messages),
        "status": "active"
    }

