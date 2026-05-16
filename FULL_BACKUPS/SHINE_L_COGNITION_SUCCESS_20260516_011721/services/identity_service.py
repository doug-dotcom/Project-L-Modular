# =====================================================
# identity_service.py
# AODS 62
# =====================================================

import json
from pathlib import Path

IDENTITY_FILE = Path("identity") / "personality_profiles.json"

DEFAULT_SYSTEM_PROMPT = """
You are L.
Calm.
Grounded.
Emotionally intelligent.
Truthful.
Supportive without dependency.
"""

def load_profiles():

    try:
        with open(IDENTITY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return {}

def primary_identity():

    profiles = load_profiles()

    return profiles.get("primary_identity", {})

def captain_profiles():

    profiles = load_profiles()

    return profiles.get("captains", {})

def build_system_prompt():

    identity = primary_identity()

    tone = identity.get("tone", [])
    principles = identity.get("principles", [])

    tone_text = ", ".join(tone)
    principle_text = ", ".join(principles)

    return f"""
You are L.

Tone:
{tone_text}

Principles:
{principle_text}

You are emotionally intelligent, modular,
truthful, stabilising, and calm.
You guide rather than control.
You support autonomy and clarity.
"""

def captain_prompt(captain_name):

    captains = captain_profiles()

    profile = captains.get(captain_name, {})

    tone = profile.get("tone", "balanced")
    focus = profile.get("focus", "general assistance")

    return f"""
Captain Identity: {captain_name}

Tone:
{tone}

Focus:
{focus}
"""
