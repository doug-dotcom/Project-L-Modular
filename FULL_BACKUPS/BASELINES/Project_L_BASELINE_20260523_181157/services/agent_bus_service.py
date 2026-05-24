# =====================================================
# agent_bus_service.py
# AODS 56
# =====================================================

import json
from pathlib import Path
from datetime import datetime

BUS_DIR = Path("bus")
BUS_FILE = BUS_DIR / "agent_bus.json"

MAX_MESSAGES = 100

def ensure_bus():
    BUS_DIR.mkdir(exist_ok=True)

    if not BUS_FILE.exists():
        with open(BUS_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)

def load_bus():
    ensure_bus()

    try:
        with open(BUS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            return data

        return []

    except Exception:
        return []

def save_bus(messages):
    ensure_bus()

    messages = messages[-MAX_MESSAGES:]

    with open(BUS_FILE, "w", encoding="utf-8") as f:
        json.dump(messages, f, indent=2)

def publish_message(
    sender,
    recipient,
    message_type,
    content,
    priority="normal",
    thread_id="default",
    metadata=None
):
    messages = load_bus()

    event = {
        "timestamp": datetime.now().isoformat(),
        "sender": sender,
        "recipient": recipient,
        "message_type": message_type,
        "priority": priority,
        "thread_id": thread_id,
        "content": content,
        "metadata": metadata or {},
        "status": "published"
    }

    messages.append(event)

    save_bus(messages)

    record_event(
        event_type="bus_message",
        source=sender,
        payload=event,
        severity=priority
    )

    return event

def recent_messages(limit=20):
    return load_bus()[-limit:]

def messages_for_agent(agent_name, limit=20):
    agent_name = str(agent_name).lower()

    results = [
        m for m in load_bus()
        if str(m.get("recipient", "")).lower() == agent_name
        or str(m.get("sender", "")).lower() == agent_name
    ]

    return results[-limit:]

def bus_status():
    messages = load_bus()

    return {
        "status": "online",
        "message_count": len(messages),
        "bus_file": str(BUS_FILE)
    }

