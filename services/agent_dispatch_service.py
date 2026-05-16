# =====================================================
# agent_dispatch_service.py
# AODS 56
# =====================================================

from services.tegan_triage_service import TEGAN
from services.agent_bus_service import publish_message

def dispatch_user_message(user_message, thread_id="default"):

    triage = TEGAN.triage(user_message)

    assigned_to = triage.get("assigned_to", "L")
    category = triage.get("category", "general")
    priority = triage.get("priority", "normal")

    event = publish_message(
        sender="Doug",
        recipient=assigned_to,
        message_type=category,
        content=user_message,
        priority=priority,
        thread_id=thread_id,
        metadata={
            "triage": triage
        }
    )

    return {
        "triage": triage,
        "bus_event": event
    }
