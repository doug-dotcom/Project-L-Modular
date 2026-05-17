# =====================================================
# captain_tool_adapter_service.py
# AODS 64
# =====================================================

import json
from pathlib import Path
from datetime import datetime

TOOL_FILE = Path("tools") / "captain_tool_adapters.json"

def load_tool_adapters():

    try:
        with open(TOOL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return {
            "tool_adapters": {}
        }

def adapter_profiles():

    data = load_tool_adapters()

    return data.get("tool_adapters", {})

def captain_tools(captain_name):

    profiles = adapter_profiles()

    return profiles.get(captain_name, {
        "allowed_tools": [],
        "blocked_tools": []
    })

def tool_check(captain_name, tool_name):

    profile = captain_tools(captain_name)

    allowed = [
        str(t).lower()
        for t in profile.get("allowed_tools", [])
    ]

    blocked = [
        str(t).lower()
        for t in profile.get("blocked_tools", [])
    ]

    requested = str(tool_name).lower()

    permitted = requested in allowed
    denied = requested in blocked

    final_status = (
        "blocked"
        if denied else
        "allowed"
        if permitted else
        "unknown"
    )

    return {
        "timestamp": datetime.now().isoformat(),
        "captain": captain_name,
        "tool": tool_name,
        "status": final_status,
        "allowed_tools": profile.get("allowed_tools", []),
        "blocked_tools": profile.get("blocked_tools", [])
    }

def build_tool_runtime_card(captain_name):

    profile = captain_tools(captain_name)

    return {
        "captain": captain_name,
        "allowed_tools": profile.get("allowed_tools", []),
        "blocked_tools": profile.get("blocked_tools", []),
        "tool_count": len(profile.get("allowed_tools", []))
    }
