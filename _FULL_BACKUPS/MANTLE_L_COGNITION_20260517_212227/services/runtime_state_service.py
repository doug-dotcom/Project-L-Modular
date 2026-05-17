# =====================================================
# runtime_state_service.py
# AODS 59
# =====================================================

import json
from pathlib import Path
from datetime import datetime

STATE_DIR = Path("state")
STATE_FILE = STATE_DIR / "runtime_state.json"

DEFAULT_STATE = {
    "runtime_status": "ONLINE",
    "boot_time": None,
    "last_updated": None,
    "heartbeat_count": 0,
    "active_threads": 0,
    "active_workflows": 0,
    "active_agents": [],
    "last_event": None
}

def ensure_state():

    STATE_DIR.mkdir(exist_ok=True)

    if not STATE_FILE.exists():

        state = DEFAULT_STATE.copy()

        state["boot_time"] = datetime.now().isoformat()
        state["last_updated"] = datetime.now().isoformat()

        save_state(state)

def load_state():

    ensure_state()

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return DEFAULT_STATE.copy()

def save_state(state):

    state["last_updated"] = datetime.now().isoformat()

    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

def runtime_heartbeat():

    state = load_state()

    state["heartbeat_count"] += 1

    save_state(state)

    return state

def update_runtime_event(event_name):

    state = load_state()

    state["last_event"] = {
        "event": event_name,
        "timestamp": datetime.now().isoformat()
    }

    save_state(state)

    record_event(
        event_type="runtime_event",
        source="runtime_state_service",
        payload=state["last_event"],
        severity="normal"
    )

    return state

def register_agent(agent_name):

    state = load_state()

    agents = state.get("active_agents", [])

    if agent_name not in agents:
        agents.append(agent_name)

    state["active_agents"] = agents

    save_state(state)

    return state

def increment_threads():

    state = load_state()

    state["active_threads"] += 1

    save_state(state)

    return state

def increment_workflows():

    state = load_state()

    state["active_workflows"] += 1

    save_state(state)

    return state

def runtime_status():

    return load_state()

