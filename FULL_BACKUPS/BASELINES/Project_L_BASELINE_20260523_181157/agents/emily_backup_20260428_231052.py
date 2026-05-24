import os
import base64
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
    "https://www.googleapis.com/auth/calendar"
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
# LEVEL 2 — FULL EMAIL READER
# =========================
def extract_body(payload):
    """Recursively extract text/plain or fallback to HTML"""
    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain":
                data = part["body"].get("data")
                if data:
                    return base64.urlsafe_b64decode(data).decode("utf-8")

        for part in payload["parts"]:
            result = extract_body(part)
            if result:
                return result
    else:
        data = payload.get("body", {}).get("data")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8")

    return ""

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
# GPT EMAIL SUMMARY (UPGRADED)
# =========================
def summarise_emails_with_gpt(emails, use_full_content=False):
    client = OpenAI()

    if not emails:
        return "No emails found."

    email_text = ""

    for i, e in enumerate(emails, start=1):

        # SAFE MODE: try full email, fallback to snippet
        content = e.get("snippet", "")

        if use_full_content:
            full = get_full_email(e["id"])
            if full.get("body"):
                content = full["body"]

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

Rules:
- Be concise
- Use plain language
- Focus on actionability
- Ignore obvious promos/newsletters unless important

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
# TEST BLOCK (SAFE)
# =========================
if __name__ == "__main__":
    emails = get_emails(3)

    print("\n=== LEVEL 1 TEST ===")
    for e in emails:
        print(e["subject"])

    print("\n=== LEVEL 2 TEST ===")
    for e in emails:
        full = get_full_email(e["id"])
        print("\nBODY PREVIEW:")
        print(full.get("body", "")[:500])
