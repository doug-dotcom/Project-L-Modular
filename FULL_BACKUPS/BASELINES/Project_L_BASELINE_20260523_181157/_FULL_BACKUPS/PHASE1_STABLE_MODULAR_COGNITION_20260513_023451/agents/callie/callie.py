# =====================================================
# CALLIE CALENDAR AGENT
# =====================================================

def should_handle(message: str) -> bool:

    text = message.lower()

    triggers = [

        "calendar",
        "appointment",
        "appointments",
        "meeting",
        "meetings",
        "schedule",
        "remind me",
        "callie",
        "what am i doing",
        "what is on today"

    ]

    return any(
        t in text
        for t in triggers
    )

# =====================================================
# PLACEHOLDER RESPONSE
# =====================================================

def handle_calendar_request(message: str):

    return """

# 📅 Callie Calendar

## 🧠 Calendar Assistant Active

I am Callie, your scheduling and calendar specialist.

---

## 🔥 Current Status

Calendar orchestration is connected successfully.

Live Google Calendar integration already exists and will be connected next.

---

## 👀 What I Will Eventually Handle

- appointments
- reminders
- scheduling
- availability
- time awareness
- recurring events

---

## ✅ Current Phase

Stage 1:
Orchestration and routing.

Stage 2:
Live Google Calendar execution.

"""
