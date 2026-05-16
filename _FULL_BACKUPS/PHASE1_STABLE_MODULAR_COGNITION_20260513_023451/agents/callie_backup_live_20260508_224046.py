import datetime
import os
import re
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# =========================
# CONFIG
# =========================
BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", "configs"))

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks"
]
# =========================
# AUTH
# =========================
def get_service():
    creds = None

    token_path = os.path.join(CONFIG_PATH, "token.json")
    creds_path = os.path.join(CONFIG_PATH, "credentials.json")

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds:
        flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
        creds = flow.run_local_server(port=0)

        with open(token_path, 'w') as token:
            token.write(creds.to_json())

    return build('calendar', 'v3', credentials=creds)

# =========================
# PARSE DATE/TIME
# =========================
def parse_datetime(text):
    now = datetime.datetime.now()
    text = text.lower()

    if "tomorrow" in text:
        day = now + datetime.timedelta(days=1)
    else:
        day = now

    match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', text)

    if match:
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        ampm = match.group(3)

        if ampm == "pm" and hour != 12:
            hour += 12
        if ampm == "am" and hour == 12:
            hour = 0
    else:
        hour = 9
        minute = 0

    return day.replace(hour=hour, minute=minute, second=0)

# =========================
# ADD EVENT
# =========================
def add_event(text):
    service = get_service()

    dt = parse_datetime(text)
    title = re.sub(r'(tomorrow|today|at|\d{1,2}(:\d{2})?\s*(am|pm))', '', text, flags=re.IGNORECASE).strip()

    event = {
        'summary': title,
        'start': {'dateTime': dt.isoformat(), 'timeZone': 'Australia/Brisbane'},
        'end': {'dateTime': (dt + datetime.timedelta(hours=1)).isoformat(), 'timeZone': 'Australia/Brisbane'},
    }

    service.events().insert(calendarId='primary', body=event).execute()

    return f"ðŸ“… Added: {title} at {dt.strftime('%I:%M %p')}"

# =========================
# LIST EVENTS
# =========================
def list_events():
    service = get_service()

    now = datetime.datetime.utcnow().isoformat() + 'Z'

    events = service.events().list(
        calendarId='primary',
        timeMin=now,
        maxResults=5,
        singleEvents=True,
        orderBy='startTime'
    ).execute().get('items', [])

    if not events:
        return "No upcoming events."

    output = "ðŸ“… Upcoming:\n"

    for e in events:
        start = e['start'].get('dateTime', e['start'].get('date'))
        output += f"- {start} | {e['summary']}\n"

    return output

# =========================
# MAIN HANDLER
# =========================
def handle_calendar(text):

    text_lower = text.lower()

    if "show" in text_lower or "what" in text_lower:
        return list_events()

    return add_event(text)
