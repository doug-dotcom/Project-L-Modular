# =====================================================
# runtime_recovery_service.py
# AODS 60
# =====================================================

import json
from pathlib import Path
from datetime import datetime

ROOT = Path(".")
SERVICES = Path("services")
STATE = Path("state")
BUS = Path("bus")
THREADS = Path("threads")
MEMORY = Path("memory")
CONFIG = Path("config")
WORKFLOWS = Path("workflows")

REQUIRED_DIRS = [
    SERVICES,
    STATE,
    BUS,
    THREADS,
    MEMORY,
    CONFIG,
    WORKFLOWS
]

REQUIRED_FILES = {
    "state/runtime_state.json": {
        "runtime_status": "ONLINE",
        "boot_time": None,
        "last_updated": None,
        "heartbeat_count": 0,
        "active_threads": 0,
        "active_workflows": 0,
        "active_agents": [],
        "last_event": None
    },
    "bus/agent_bus.json": [],
    "memory/structured.json": [],
    "memory/reflections.json": [],
    "memory/episodes.json": [],
    "memory/identity.json": [],
    "memory/scratchpad.json": []
}

REQUIRED_SERVICE_FILES = [
    "services/tegan_triage_service.py",
    "services/captain_registry_service.py",
    "services/captain_action_service.py",
    "services/agent_bus_service.py",
    "services/agent_dispatch_service.py",
    "services/action_execution_service.py",
    "services/workflow_chain_service.py",
    "services/runtime_state_service.py",
    "services/thread_engine_service.py",
    "services/memory_context_service.py"
]

def timestamp():
    return datetime.now().isoformat()

def ensure_dirs():
    results = []

    for d in REQUIRED_DIRS:
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            results.append({"path": str(d), "status": "created"})
        else:
            results.append({"path": str(d), "status": "exists"})

    return results

def ensure_json_file(path_str, default_value):
    path = Path(path_str)

    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        if isinstance(default_value, dict):
            data = dict(default_value)
            if "boot_time" in data and not data["boot_time"]:
                data["boot_time"] = timestamp()
            if "last_updated" in data and not data["last_updated"]:
                data["last_updated"] = timestamp()
        else:
            data = default_value

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        return {"path": path_str, "status": "created"}

    try:
        with open(path, "r", encoding="utf-8") as f:
            json.load(f)

        return {"path": path_str, "status": "valid"}

    except Exception:
        corrupt_path = path.with_suffix(path.suffix + ".corrupt_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
        path.rename(corrupt_path)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(default_value, f, indent=2)

        return {
            "path": path_str,
            "status": "repaired",
            "corrupt_backup": str(corrupt_path)
        }

def check_service_files():
    results = []

    for file_path in REQUIRED_SERVICE_FILES:
        path = Path(file_path)

        if path.exists():
            results.append({"path": file_path, "status": "exists"})
        else:
            results.append({"path": file_path, "status": "missing"})

    return results

def recovery_scan():
    return {
        "timestamp": timestamp(),
        "directories": ensure_dirs(),
        "json_files": [
            ensure_json_file(path, default)
            for path, default in REQUIRED_FILES.items()
        ],
        "service_files": check_service_files(),
        "status": "scan_complete"
    }

def recovery_summary():
    scan = recovery_scan()

    missing_services = [
        item for item in scan["service_files"]
        if item["status"] == "missing"
    ]

    repaired_json = [
        item for item in scan["json_files"]
        if item["status"] in ["created", "repaired"]
    ]

    return {
        "timestamp": timestamp(),
        "status": "healthy" if not missing_services else "attention_required",
        "missing_service_count": len(missing_services),
        "missing_services": missing_services,
        "json_repairs_or_creations": repaired_json
    }

def self_heal():
    scan = recovery_scan()
    summary = recovery_summary()

    return {
        "timestamp": timestamp(),
        "scan": scan,
        "summary": summary,
        "self_heal_status": summary["status"]
    }
