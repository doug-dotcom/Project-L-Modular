import json
import os
from datetime import datetime
# ============================================================
# RUNTIME BOOTSTRAP
# Phase 13 - Server.py Collapse
# Central runtime construction layer
# ============================================================

from orchestration.runtime_engine import (
    RuntimeEngine,
)

from orchestration.tegan_runtime import (
    MajorTeganRuntime,
)

from memory.orchestrator import (
    memory_orchestration_status,
)

from orchestration.active_registry import (
    get_active_captains,
)

from core.config import *
from core.paths import *

from openai import OpenAI


def build_runtime_stack():

    runtime_engine = RuntimeEngine()

    tegan_runtime = MajorTeganRuntime()

    return {
        "runtime_engine": runtime_engine,
        "tegan_runtime": tegan_runtime,
    }


def build_runtime_status():

    captains = get_active_captains()

    return {
        "status": "online",
        "phase": "server_collapse",
        "runtime_engine": "active",
        "tegan_runtime": "active",
        "captain_count": len(captains),
        "memory": memory_orchestration_status(),
    }

# =========================================================
# RUNTIME CHAT BRIDGE
# =========================================================


async def handle_chat(req):

    message = getattr(req, "message", "")

    request_type = classify_request(message)

    operational_state = determine_operational_state(message)

    active_captain = dispatch_captain(
        message,
        request_type
    )

    log_runtime_event(
        "operational_state_detected",
        {
            "state": operational_state
        }
    )

    log_runtime_event(
        "captain_dispatched",
        {
            "captain": active_captain,
            "request_type": request_type
        }
    )

    log_runtime_event(
        "chat_request_received",
        {
            "message": message,
            "request_type": request_type
        }
    )

    if not message:

        return {
            "reply": "I did not receive a message."
        }

    try:

        recent_memories = get_recent_memories()

        memory_context = json.dumps(
            recent_memories,
            indent=2
        )

        memory_search_results = json.dumps(
            search_memories(message),
            indent=2
        )

        messages = [

            {
                "role": "system",
                "content": "you are L, a modular AI runtime operating through Tegan orchestration."
            },

            {
                "role": "user",
                "content": message
            }
        ]

        reply = protected_openai_call(messages)

       

        log_runtime_event(
            "openai_response_success",
            {
                "request_type": request_type
            }
        )

        save_memory(message, reply)

        return {
            "reply": reply,
            "runtime": "tegan_runtime",
            "status": "online",
            "cognition": "openai_live",
            "request_type": request_type
        }

    except Exception as e:

        log_runtime_event(
            "openai_response_failure",
            {
                "error": str(e)
            }
        )

        return {
            "reply": f"AI cognition error: {str(e)}",
            "runtime": "tegan_runtime",
            "status": "degraded"
        }



# =========================================================
# AI CLIENT
# =========================================================

client = OpenAI()






# =====================================================
# ELLIE MEMORY
# =====================================================

MEMORY_DIR = "memory"

MEMORY_FILE = os.path.join(
    MEMORY_DIR,
    "conversations.json"
)

os.makedirs(MEMORY_DIR, exist_ok=True)

def save_memory(user_message, l_reply):

    memory_entry = {
        "timestamp": datetime.now().isoformat(),
        "user": user_message,
        "l_reply": l_reply
    }

    memories = []

    if os.path.exists(MEMORY_FILE):

        try:

            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                memories = safe_json_load(MEMORY_FILE, [])

        except:
            memories = []

    memories.append(memory_entry)

    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memories[-50:], f, indent=2)




# =====================================================
# MEMORY RETRIEVAL
# =====================================================

def get_recent_memories(limit=5):

    if not os.path.exists(MEMORY_FILE):
        return []

    try:

        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            memories = safe_json_load(MEMORY_FILE, [])

        return memories[-limit:]

    except:
        return []




# =====================================================
# TEGAN REQUEST CLASSIFIER
# =====================================================

def classify_request(message):

    text = (message or "").lower()

    if any(word in text for word in [
        "remember",
        "memory",
        "recall",
        "earlier",
        "before"
    ]):

        return "memory_recall"

    if any(word in text for word in [
        "runtime",
        "status",
        "health",
        "system",
        "online"
    ]):

        return "runtime_query"

    if any(word in text for word in [
        "emily",
        "brittany",
        "captain"
    ]):

        return "captain_route"

    return "general_chat"




# =====================================================
# SESSION MEMORY
# =====================================================

SESSION_FILE = os.path.join(
    MEMORY_DIR,
    "sessions.json"
)

CURRENT_SESSION_ID = datetime.now().strftime(
    "%Y%m%d_%H%M%S"
)

def generate_session_title(message):

    text = (message or "").strip()

    if not text:
        return "Untitled Session"

    words = text.split()

    return " ".join(words[:6])

def save_session_memory(user_message, l_reply):

    session_entry = {
        "session_id": CURRENT_SESSION_ID,
        "timestamp": datetime.now().isoformat(),
        "title": generate_session_title(user_message),
        "user": user_message,
        "l_reply": l_reply
    }

    sessions = []

    if os.path.exists(SESSION_FILE):

        try:

            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                sessions = safe_json_load(MEMORY_FILE, [])

        except:
            sessions = []

    sessions.append(session_entry)

    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(sessions[-200:], f, indent=2)




# =====================================================
# CAPTAIN REGISTRY
# =====================================================

CAPTAIN_FILE = os.path.join(
    MEMORY_DIR,
    "captains.json"
)

def load_captains():

    if not os.path.exists(CAPTAIN_FILE):
        return []

    try:

        with open(CAPTAIN_FILE, "r", encoding="utf-8") as f:
            return safe_json_load(MEMORY_FILE, [])

    except:
        return []

def get_active_captains():

    captains = load_captains()

    return [
        c for c in captains
        if c.get("status") == "online"
    ]




# =====================================================
# RUNTIME SELF REFLECTION
# =====================================================

def build_runtime_reflection():

    try:
        memory_count = len(get_recent_memories(50))
    except:
        memory_count = 0

    try:
        captains = get_active_captains()
    except:
        captains = []

    reflection = {
        "runtime": "tegan_runtime",
        "runtime_status": "online",
        "cognition": "openai_live",
        "memory_entries": memory_count,
        "captain_count": len(captains),
        "captains": [
            c.get("name")
            for c in captains
        ],
        "memory_file": MEMORY_FILE,
        "session_file": SESSION_FILE,
        "current_session": CURRENT_SESSION_ID
    }

    return reflection




# =====================================================
# MEMORY SEARCH
# =====================================================

def search_memories(query, limit=5):

    if not os.path.exists(MEMORY_FILE):
        return []

    try:

        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            memories = safe_json_load(MEMORY_FILE, [])

    except:
        return []

    q = (query or "").lower()

    results = []

    for memory in reversed(memories):

        user_text = str(memory.get("user", "")).lower()
        l_text = str(memory.get("l_reply", "")).lower()

        if q in user_text or q in l_text:
            results.append(memory)

        if len(results) >= limit:
            break

    return results




# =====================================================
# RUNTIME EVENT LOG
# =====================================================

RUNTIME_EVENT_FILE = os.path.join(
    MEMORY_DIR,
    "runtime_events.json"
)

def log_runtime_event(event_type, details=None):

    event_entry = {
        "timestamp": datetime.now().isoformat(),
        "event_type": event_type,
        "details": details or {}
    }

    events = []

    if os.path.exists(RUNTIME_EVENT_FILE):

        try:

            with open(RUNTIME_EVENT_FILE, "r", encoding="utf-8") as f:
                events = safe_json_load(MEMORY_FILE, [])

        except:
            events = []

    events.append(event_entry)

    with open(RUNTIME_EVENT_FILE, "w", encoding="utf-8") as f:
        json.dump(events[-500:], f, indent=2)




# =====================================================
# OPERATIONAL EMOTIONAL STATE
# =====================================================

def determine_operational_state(message):

    text = (message or "").lower()

    if any(word in text for word in [
        "sad",
        "hurt",
        "lonely",
        "afraid",
        "overwhelmed"
    ]):
        return "reflective"

    if any(word in text for word in [
        "excited",
        "boom",
        "awesome",
        "amazing",
        "great"
    ]):
        return "energized"

    if any(word in text for word in [
        "fix",
        "debug",
        "runtime",
        "system",
        "repair"
    ]):
        return "focused"

    return "calm"




# =====================================================
# CAPTAIN DISPATCH ENGINE
# =====================================================

def dispatch_captain(message, request_type):

    text = (message or "").lower()

    if request_type == "memory_recall":
        return "Ellie"

    if any(word in text for word in [
        "sad",
        "hurt",
        "lonely",
        "afraid",
        "emotional"
    ]):
        return "Emily"

    if any(word in text for word in [
        "plan",
        "organize",
        "build",
        "execute",
        "strategy"
    ]):
        return "Brittany"

    return "L"




# =====================================================
# MEMORY SUMMARIZATION
# =====================================================

SUMMARY_FILE = os.path.join(
    MEMORY_DIR,
    "memory_summaries.json"
)

def build_memory_summary():

    recent = get_recent_memories(15)

    if not recent:
        return {
            "summary": "No memories available yet."
        }

    themes = []

    for memory in recent:

        text = (
            str(memory.get("user", "")) + " " +
            str(memory.get("l_reply", ""))
        ).lower()

        if "runtime" in text:
            themes.append("runtime stabilization")

        if "memory" in text:
            themes.append("memory systems")

        if "captain" in text:
            themes.append("captain orchestration")

        if "ui" in text:
            themes.append("frontend interaction")

    unique_themes = list(set(themes))

    summary = {
        "timestamp": datetime.now().isoformat(),
        "themes": unique_themes,
        "memory_count": len(recent)
    }

    summaries = []

    if os.path.exists(SUMMARY_FILE):

        try:

            with open(SUMMARY_FILE, "r", encoding="utf-8") as f:
                summaries = safe_json_load(MEMORY_FILE, [])

        except:
            summaries = []

    summaries.append(summary)

    with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
        json.dump(summaries[-50:], f, indent=2)

    return summary

def get_latest_summary():

    if not os.path.exists(SUMMARY_FILE):
        return {}

    try:

        with open(SUMMARY_FILE, "r", encoding="utf-8") as f:
            summaries = safe_json_load(MEMORY_FILE, [])

        if summaries:
            return summaries[-1]

    except:
        return {}

    return {}




# =====================================================
# RUNTIME PROTECTION LAYER
# =====================================================

def safe_json_load(path, fallback=None):

    fallback = fallback or []

    if not os.path.exists(path):
        return fallback

    try:

        with open(path, "r", encoding="utf-8") as f:
            return safe_json_load(MEMORY_FILE, [])

    except Exception as e:

        log_runtime_event(
            "json_load_failure",
            {
                "path": path,
                "error": str(e)
            }
        )

        return fallback

def protected_openai_call(messages):

    try:

        response = client.chat.completions.create(
            model="gpt-5.5",
            messages=messages
        )

        reply = response.choices[0].message.content

        if not reply or len(reply.strip()) == 0:

            log_runtime_event(
                "empty_ai_response",
                {}
            )

            return (
                "I am operational, but I could not "
                "generate a response safely."
            )

        return reply

    except Exception as e:

        log_runtime_event(
            "openai_runtime_failure",
            {
                "error": str(e)
            }
        )

        return (
            f"AI cognition error: {str(e)}"
        )

# =====================================================
# PROTECTION LAYER ACTIVATION
# =====================================================

log_runtime_event(
    "runtime_protection_enabled",
    {
        "status": "online"
    }
)




# ============================================================
# SAFE MEMORY LOADER
# ============================================================

def safe_memory_load(path, fallback=None):

    fallback = fallback or []

    try:

        if not os.path.exists(path):
            return fallback

        with open(
            path,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        return data

    except Exception as e:

        try:

            log_runtime_event(
                "safe_memory_load_failure",
                {
                    "path": path,
                    "error": str(e)
                }
            )

        except:
            pass

        return fallback


