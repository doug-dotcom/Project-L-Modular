# =====================================================
# guardian_service.py
# AODS 61
# =====================================================

import json
import time
from pathlib import Path
from datetime import datetime

from services.runtime_state_service import (
    runtime_heartbeat,
    runtime_status,
    update_runtime_event
)

from services.runtime_confidence_service import runtime_alignment
from services.runtime_strategy_service import strategic_snapshot
from services.runtime_mission_control_service import command_brief
from services.runtime_recovery_service import (
    recovery_summary,
    self_heal
)

GUARDIAN_DIR = Path("guardian")
LOG_DIR = Path("logs")

GUARDIAN_STATE = GUARDIAN_DIR / "guardian_state.json"
WATCHDOG_LOG = LOG_DIR / "watchdog.log"

LOOP_DELAY_SECONDS = 15

def ensure_guardian():

    GUARDIAN_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)

    if not GUARDIAN_STATE.exists():

        state = {
            "guardian_status": "ONLINE",
            "boot_time": timestamp(),
            "last_loop": None,
            "loop_count": 0,
            "last_recovery_status": None
        }

        save_guardian_state(state)

def timestamp():
    return datetime.now().isoformat()

def load_guardian_state():

    ensure_guardian()

    try:
        with open(GUARDIAN_STATE, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return {
            "guardian_status": "ERROR"
        }

def save_guardian_state(state):

    with open(GUARDIAN_STATE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

def write_log(message):

    ensure_guardian()

    line = f"[{timestamp()}] {message}\n"

    with open(WATCHDOG_LOG, "a", encoding="utf-8") as f:
        f.write(line)

def guardian_status():

    return load_guardian_state()

def watchdog_cycle():

    state = load_guardian_state()

    heartbeat = runtime_heartbeat()

    recovery = recovery_summary()

    alignment = runtime_alignment()

    state["last_alignment"] = alignment

    state["last_strategy"] = strategic_snapshot()

    state["last_command_brief"] = command_brief()

    state["last_loop"] = timestamp()
    state["loop_count"] = state.get("loop_count", 0) + 1
    state["last_recovery_status"] = recovery.get("status")

    save_guardian_state(state)

    update_runtime_event("guardian_watchdog_cycle")

    write_log(
        f"heartbeat={heartbeat.get('heartbeat_count')} "
        f"recovery={recovery.get('status')}"
    )

    if recovery.get("status") != "healthy":

        write_log("guardian_triggered_self_heal")

        heal = self_heal()

        return {
            "guardian": state,
            "heartbeat": heartbeat,
            "recovery": recovery,
            "self_heal": heal,
            "status": "self_heal_triggered"
        }

    return {
        "guardian": state,
        "heartbeat": heartbeat,
        "recovery": recovery,
        "status": "healthy"
    }

def watchdog_loop(iterations=1):

    results = []

    for _ in range(iterations):

        results.append(
            watchdog_cycle()
        )

        time.sleep(LOOP_DELAY_SECONDS)

    return results



