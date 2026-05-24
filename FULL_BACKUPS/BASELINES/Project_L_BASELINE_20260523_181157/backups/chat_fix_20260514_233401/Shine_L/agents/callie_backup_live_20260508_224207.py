from datetime import datetime

from api.google_auth import (
    get_google_service
)

# =====================================================
# ROUTING
# =====================================================

def should_handle(message: str) -> bool:

    text = message.lower()

    triggers = [

        "calendar",
        "schedule",
        "appointment",
        "appointments",
        "meeting",
        "meetings",
        "event",
        "events",
        "what do i have on",
        "what is on today",
        "callie"

    ]

    return any(
        t in text
        for t in triggers
    )

# =====================================================
# LIST EVENTS
# =====================================================

def get_events():

    service = get_google_service(
        "calendar",
        "v3"
    )

    now = datetime.utcnow().isoformat() + "Z"

    results = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now,
            maxResults=10,
            singleEvents=True,
            orderBy="startTime"
        )
        .execute()
    )

    events = results.get(
        "items",
        []
    )

    return events

# =====================================================
# FORMAT EVENTS
# =====================================================

def summarize_events(events):

    if not events:

        return """

# 📅 Callie Calendar

No upcoming events found.

"""

    output = """

# 📅 Callie Calendar

## 👀 Upcoming Events

"""

    for e in events:

        start = (
            e["start"]
            .get(
                "dateTime",
                e["start"].get("date")
            )
        )

        title = e.get(
            "summary",
            "Untitled Event"
        )

        output += f"""

- {start}
  → {title}

"""

    return output

# =====================================================
# MAIN HANDLER
# =====================================================

def handle_calendar_request(message: str):

    try:

        events = get_events()

        return summarize_events(
            events
        )

    except Exception as e:

        return f"""

# 📅 Callie Calendar

## ❌ Calendar Error

{str(e)}

"""
