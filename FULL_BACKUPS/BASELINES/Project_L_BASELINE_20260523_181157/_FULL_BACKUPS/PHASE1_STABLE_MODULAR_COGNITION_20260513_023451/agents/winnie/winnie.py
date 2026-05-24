import os
import json
import re
from datetime import datetime

ROOT_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        ".."
    )
)

WHATSAPP_FILE = os.path.join(
    ROOT_DIR,
    "memory",
    "winnie_whatsapp.json"
)

os.makedirs(
    os.path.dirname(WHATSAPP_FILE),
    exist_ok=True
)

# =====================================================
# LOAD / SAVE
# =====================================================

def _load():

    try:

        if not os.path.exists(WHATSAPP_FILE):

            return []

        with open(
            WHATSAPP_FILE,
            "r",
            encoding="utf-8"
        ) as f:

            data = json.load(f)

        if isinstance(data, list):

            return data

        return []

    except Exception as e:

        print("WINNIE LOAD ERROR:", e)

        return []


def _save(data):

    try:

        with open(
            WHATSAPP_FILE,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                data,
                f,
                indent=2,
                ensure_ascii=False
            )

    except Exception as e:

        print("WINNIE SAVE ERROR:", e)

# =====================================================
# ROUTING DETECTION
# =====================================================

def should_handle(message: str) -> bool:

    text = message.lower()

    triggers = [

        "winnie",
        "whatsapp",
        "chat summary",
        "message summary",
        "analyze chat",
        "extract events",
        "extract actions",
        "social coordination",
        "conversation summary"

    ]

    return any(
        phrase in text
        for phrase in triggers
    )

# =====================================================
# SAVE CHAT
# =====================================================

def save_chat(message):

    chats = _load()

    entry = {

        "timestamp":
            datetime.now().isoformat(),

        "message":
            message,

        "events":
            extract_events(message),

        "actions":
            extract_actions(message)

    }

    chats.append(entry)

    _save(chats)

    return entry

# =====================================================
# EVENT EXTRACTION
# =====================================================

def extract_events(text):

    events = []

    keywords = [

        "game",
        "meeting",
        "training",
        "session",
        "birthday",
        "event",
        "appointment"

    ]

    if any(
        word in text.lower()
        for word in keywords
    ):

        events.append(text)

    return events

# =====================================================
# ACTION EXTRACTION
# =====================================================

def extract_actions(text):

    actions = []

    keywords = [

        "bring",
        "pay",
        "confirm",
        "rsvp",
        "need to",
        "call",
        "book",
        "send"

    ]

    if any(
        word in text.lower()
        for word in keywords
    ):

        actions.append(text)

    return actions

# =====================================================
# BUILD SUMMARY
# =====================================================

def build_summary(entry):

    reply = "# 💬 Winnie WhatsApp Cognition\n\n"

    reply += (
        "WhatsApp/social message analyzed successfully.\n\n"
    )

    if entry.get("events"):

        reply += "## 📅 Possible Events\n\n"

        for e in entry.get("events"):

            reply += "- " + e + "\n"

        reply += "\n"

    if entry.get("actions"):

        reply += "## ✅ Possible Action Items\n\n"

        for a in entry.get("actions"):

            reply += "- " + a + "\n"

        reply += "\n"

    if (
        not entry.get("events")
        and not entry.get("actions")
    ):

        reply += (
            "No strong events or action items detected yet."
        )

    return reply

# =====================================================
# LIST ANALYSIS
# =====================================================

def list_chats():

    chats = _load()

    if not chats:

        return (
            "# 💬 Winnie WhatsApp Cognition\n\n"
            "No WhatsApp analyses stored yet."
        )

    reply = "# 💬 Winnie WhatsApp Cognition\n\n"

    reply += "Recent chat analyses:\n\n"

    latest = chats[-5:]

    for i, item in enumerate(reversed(latest), start=1):

        reply += (
            f"## Analysis {i}\n"
            + item.get("message","")
            + "\n\n"
        )

    return reply

# =====================================================
# MAIN HANDLER
# =====================================================

def handle_whatsapp_request(message: str):

    text = message.lower()

    if (
        "show chats" in text
        or "list chats" in text
        or "show analyses" in text
    ):

        return list_chats()

    entry = save_chat(message)

    return build_summary(entry)
