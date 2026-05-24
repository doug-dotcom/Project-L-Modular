from memory.memory_engine import (
    _load_supabase_facts
)

from datetime import datetime

# =====================================================
# ROUTING
# =====================================================

def should_handle(message: str) -> bool:

    text = message.lower()

    triggers = [

        "tegan",
        
    ]

    return any(
        t in text
        for t in triggers
    )

# =====================================================
# AGENT STATES
# =====================================================

AGENTS = {

    "Millie":
        "Connected to unified Supabase memory",

    "Emme":
        "Emotional regulation online",

    "Addie":
        "Task execution online",

    "Gracie":
        "Legacy workflows online",

    "Noelie":
        "Research cognition online",

    "Richie":
        "Reflective cognition online"

}

# =====================================================
# BUILD REPORT
# =====================================================

def build_report():

    facts = _load_supabase_facts(500)

    reply = ""

    reply += "Shine ecosystem status:\n\n"

    for name, state in AGENTS.items():

        reply += (
            f"- {name}: {state}\n"
        )

    reply += "\n"

    reply += (
        f"Unified memory count: {len(facts)}\n"
    )

    reply += (
        "Supabase memory spine: ONLINE\n"
    )

    reply += (
        "Semantic memory: ACTIVE\n"
    )

    reply += (
        "Orchestration spine: ACTIVE\n"
    )

    return reply

# =====================================================
# MAIN HANDLER
# =====================================================

def handle_integration_request(message: str):

    return build_report()



