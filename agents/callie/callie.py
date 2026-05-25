from api.google_auth import (
    get_google_service
)

def should_handle(message: str) -> bool:

    text = (message or "").lower()

    triggers = [

        "calendar",
        "meeting",
        "schedule",
        "appointment",
        "callie",
        "what is on today"

    ]

    return any(
        t in text
        for t in triggers
    )

def get_events():

    service = get_google_service(
        "calendar",
        "v3"
    )

    results = (
        service.events()
        .list(
            calendarId="primary",
            maxResults=10,
            singleEvents=True,
            orderBy="startTime"
        )
        .execute()
    )

    return results.get(
        "items",
        []
    )

def handle_calendar_request(message: str):

    try:

        events = get_events()

        output = "# 📅 Callie Calendar\n\n"

        if not events:

            output += "No upcoming events."

            return output

        for e in events:

            start = (
                e.get("start", {})
                .get("dateTime", "")
            )

            summary = e.get(
                "summary",
                "Untitled"
            )

            output += (
                f"- {summary}"
                + "\n"
                + f"  {start}"
                + "\n\n"
            )

        return output

    except Exception as e:

        return f"""

# 📅 Callie Error

{str(e)}

IMPORTANT:
You probably need:
- credentials.json
- first-time Google login

"""
