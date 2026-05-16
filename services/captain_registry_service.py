# =====================================================
# captain_registry_service.py
# AODS 52
# =====================================================

import json
from pathlib import Path
from datetime import datetime

REGISTRY_PATH = Path("config") / "captain_registry.json"

DEFAULT_CAPTAIN = {
    "name": "L",
    "rank": "Lieutenant Colonel",
    "role": "Front-facing strategic command",
    "status": "active",
    "service_key": "general"
}

def load_registry():
    try:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "version": "fallback",
            "captains": {
                "general": DEFAULT_CAPTAIN
            }
        }

def list_captains():
    registry = load_registry()
    return registry.get("captains", {})

def get_captain(category: str):
    registry = load_registry()
    captains = registry.get("captains", {})
    return captains.get(category, DEFAULT_CAPTAIN)

def assign_captain(category: str):
    captain = get_captain(category)

    return {
        "timestamp": datetime.now().isoformat(),
        "category": category,
        "assigned_to": captain.get("name", "L"),
        "rank": captain.get("rank", "Lieutenant Colonel"),
        "role": captain.get("role", "Front-facing strategic command"),
        "status": captain.get("status", "active"),
        "service_key": captain.get("service_key", "general")
    }

def registry_status():
    registry = load_registry()
    captains = registry.get("captains", {})

    return {
        "registry_version": registry.get("version", "unknown"),
        "captain_count": len(captains),
        "captains": {
            key: value.get("name", key)
            for key, value in captains.items()
        }
    }
