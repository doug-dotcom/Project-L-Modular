import os
import base64
import re
from bs4 import BeautifulSoup
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from openai import OpenAI

# =========================
# PATH CONFIG
# =========================
BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.abspath(os.path.join(BASE_DIR, "..", "configs"))

# =========================
# GMAIL SCOPES
# =========================
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks"
]
# =========================
# GET GMAIL SERVICE
# =========================
def get_service():
    creds = None

    token_path = os.path.join(CONFIG_PATH, "token.json")
    creds_path = os.path.join(CONFIG_PATH, "credentials.json")

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds:
        flow = InstalledAppFlow.from_client_secrets_file(
            creds_path,
            SCOPES
        )
        creds = flow.run_local_server(port=0)

        with open(token_path, "w") as token:
            token.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)

# =========================
# FETCH EMAILS (LEVEL 1)
# =========================
def get_emails(max_results=10):
    service = get_service()

    results = service.users().messages().list(
        userId="me",
        maxResults=max_results,
        labelIds=["INBOX"]
    ).execute()

    messages = results.get("messages", [])
    emails = []

    for msg in messages:
        data = service.users().messages().get(
            userId="me",
            id=msg["id"],
            format="metadata",
            metadataHeaders=["From", "Subject", "Date"]
        ).execute()

        headers = data.get("payload", {}).get("headers", [])
        header_map = {h["name"]: h["value"] for h in headers}

        emails.append({
            "id": msg["id"],
            "from": header_map.get("From", ""),
            "subject": header_map.get("Subject", ""),
            "date": header_map.get("Date", ""),
            "snippet": data.get("snippet", "")
        })

    return emails

# =========================
# EMAIL BODY EXTRACTION
# =========================
def extract_body(payload):
    if "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain":
                data = part["body"].get("data")
                if data:
                    return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

        for part in payload["parts"]:
            result = extract_body(part)
            if result:
                return result
    else:
        data = payload.get("body", {}).get("data")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

    return ""

# =========================
# LEVEL 2.5 — FULL EMAIL READER + CLEAN
# =========================
def get_full_email(message_id):
    try:
        service = get_service()

        msg = service.users().messages().get(
            userId="me",
            id=message_id,
            format="full"
        ).execute()

        payload = msg.get("payload", {})
        body = extract_body(payload)

        # CLEAN HTML
        if body and ("<html" in body.lower() or "<div" in body.lower()):
            try:
                soup = BeautifulSoup(body, "html.parser")
                body = soup.get_text(separator="\n")
            except Exception:
                pass

        return {
            "id": message_id,
            "snippet": msg.get("snippet", ""),
            "body": body[:3000] if body else ""
        }

    except Exception as e:
        return {
            "id": message_id,
            "error": str(e)
        }

# =========================
# LEVEL 3 — SMART FLIGHT EXTRACTION
# =========================
def extract_flight_info(text):
    try:
        keywords = ["flight", "itinerary", "departure", "arrival", "jetstar", "qantas"]

        if not any(k in text.lower() for k in keywords):
            return {}

        flight = {}

        match = re.search(r'\b([A-Z]{2}\d{3,4})\b', text)
        if match:
            flight["flight_number"] = match.group(1)

        times = re.findall(r'(\d{1,2}:\d{2}\s?(AM|PM))', text)
        if len(times) >= 2:
            flight["departure_time"] = times[0][0]
            flight["arrival_time"] = times[1][0]

        if "brisbane" in text.lower():
            flight["from"] = "Brisbane"
        if "cairns" in text.lower():
            flight["to"] = "Cairns"

        if "flight_number" in flight or "departure_time" in flight:
            flight["type"] = "flight"
            return flight

        return {}

    except Exception:
        return {}

# =========================
# GPT EMAIL SUMMARY (FINAL)
# =========================
def summarise_emails_with_gpt(emails):
    client = OpenAI()

    if not emails:
        return "No emails found."

    email_text = ""

    for i, e in enumerate(emails, start=1):
        full = get_full_email(e["id"])
        content = full.get("body") if full.get("body") else e.get("snippet", "")

        email_text += f"""
EMAIL {i}
From: {e['from']}
Subject: {e['subject']}
Date: {e['date']}
Content: {content}
---
"""

    prompt = f"""
You are Emily, an inbox assistant for Doug.

Your job:
1. Identify the most important emails
2. Separate noise from signal
3. Suggest what Doug should do next

Output EXACTLY this format:

TOP PRIORITIES
1. ...
2. ...
3. ...

CAN WAIT
- ...

LIKELY NOISE
- ...

SUGGESTED ACTIONS
- ...

Here are the emails:
{email_text}
"""

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "You are a precise, practical email triage assistant."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    return response.choices[0].message.content

# =========================
# TEST BLOCK (LEVEL 3)
# =========================
if __name__ == "__main__":
    emails = get_emails(3)

    print("\n=== LEVEL 3 TEST ===")

    for e in emails:
        full = get_full_email(e["id"])
        text = full.get("body", "")

        print("\n--- EMAIL ---")
        print(text[:300])

        flight = extract_flight_info(text)

        if flight:
            print("\n🔥 FLIGHT DETECTED:")
            print(flight)