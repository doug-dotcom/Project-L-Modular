# =====================================================
# captain_specialisation_service.py
# AODS 63
# =====================================================

import json
from pathlib import Path
from datetime import datetime

SPECIALISATION_FILE = Path("captains") / "captain_specialisations.json"

def load_specialisations():

    try:
        with open(SPECIALISATION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return {
            "version": "fallback",
            "captains": {}
        }

def list_specialisations():

    data = load_specialisations()

    return data.get("captains", {})

def get_specialisation(captain_name):

    captains = list_specialisations()

    return captains.get(captain_name, {
        "domain": "general",
        "capabilities": [],
        "safe_boundaries": [],
        "runtime_status": "unknown"
    })

def capability_check(captain_name, requested_capability):

    profile = get_specialisation(captain_name)

    requested = str(requested_capability).lower()

    capabilities = [
        str(c).lower()
        for c in profile.get("capabilities", [])
    ]

    matched = any(
        requested in c or c in requested
        for c in capabilities
    )

    return {
        "timestamp": datetime.now().isoformat(),
        "captain": captain_name,
        "requested_capability": requested_capability,
        "domain": profile.get("domain"),
        "matched": matched,
        "available_capabilities": profile.get("capabilities", []),
        "safe_boundaries": profile.get("safe_boundaries", [])
    }

def captain_runtime_card(captain_name):

    profile = get_specialisation(captain_name)

    return {
        "captain": captain_name,
        "domain": profile.get("domain"),
        "runtime_status": profile.get("runtime_status"),
        "capabilities": profile.get("capabilities", []),
        "safe_boundaries": profile.get("safe_boundaries", [])
    }
