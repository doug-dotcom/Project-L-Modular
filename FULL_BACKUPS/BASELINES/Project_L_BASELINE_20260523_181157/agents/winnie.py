import os
import re
from datetime import datetime

WHATSAPP_DIR = "C:/Shine_L/memory/whatsapp"

def load_chat():
    files = os.listdir(WHATSAPP_DIR)

    for f in files:
        if f.endswith(".txt"):
            path = os.path.join(WHATSAPP_DIR, f)
            with open(path, encoding="utf-8") as file:
                return file.readlines()

    return []

def extract_events(lines):
    events = []

    date_pattern = r"\d{1,2}/\d{1,2}/\d{2,4}"
    time_pattern = r"\d{1,2}(:\d{2})?\s?(am|pm)"

    for line in lines:
        if re.search(date_pattern, line, re.IGNORECASE) or re.search(time_pattern, line, re.IGNORECASE):
            if any(keyword in line.lower() for keyword in ["game", "meet", "training", "session", "event"]):
                events.append(line.strip())

    return events[:10]

def extract_actions(lines):
    actions = []

    for line in lines:
        if any(word in line.lower() for word in ["bring", "pay", "confirm", "rsvp", "need to"]):
            actions.append(line.strip())

    return actions[:10]

def analyse_whatsapp():
    lines = load_chat()

    if not lines:
        return "No WhatsApp chat found."

    events = extract_events(lines)
    actions = extract_actions(lines)

    response = "Here’s what I found from your WhatsApp:\n\n"

    if events:
        response += "📅 Events:\n"
        for e in events:
            response += f"- {e}\n"

    if actions:
        response += "\n✅ Action items:\n"
        for a in actions:
            response += f"- {a}\n"

    return response
