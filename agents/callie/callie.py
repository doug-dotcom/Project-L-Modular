def should_handle(message: str) -> bool:

    text = (message or "").lower()

    triggers = [

        "calendar",
        "appointment",
        "meeting",
        "schedule",
        "callie"

    ]

    return any(
        t in text
        for t in triggers
    )

def handle_calendar_request(message: str):

    return """

# 📅 Callie Calendar

Callie is online.

Ready for:
- calendar events
- scheduling
- reminders
- time awareness

"""
