import re
import base64

from openai import OpenAI

from api.google_auth import (
    get_google_service
)

client = OpenAI()

# =====================================================
# ROUTING
# =====================================================

def should_handle(message: str) -> bool:

    text = message.lower()

    triggers = [

        "email",
        "emails",
        "gmail",
        "inbox",
        "check my email",
        "check my emails",
        "important emails",
        "priority emails",
        "summarize inbox",
        "summarise inbox",
        "did i get any emails",
        "emily"

    ]

    return any(
        t in text
        for t in triggers
    )

# =====================================================
# BODY EXTRACTION
# =====================================================

def extract_plain_text(payload):

    try:

        body_data = (
            payload
            .get("body", {})
            .get("data")
        )

        if body_data:

            decoded = base64.urlsafe_b64decode(
                body_data
            ).decode("utf-8", errors="ignore")

            return decoded

        parts = payload.get("parts", [])

        for part in parts:

            mime = part.get("mimeType", "")

            if mime == "text/plain":

                data = (
                    part
                    .get("body", {})
                    .get("data")
                )

                if data:

                    decoded = base64.urlsafe_b64decode(
                        data
                    ).decode("utf-8", errors="ignore")

                    return decoded

        return ""

    except Exception as e:

        print("BODY EXTRACTION ERROR:", e)

        return ""

# =====================================================
# GET EMAILS
# =====================================================

def get_emails(max_results=5):

    service = get_google_service(
        "gmail",
        "v1"
    )

    results = (
        service.users()
        .messages()
        .list(
            userId="me",
            maxResults=max_results,
            labelIds=["INBOX"]
        )
        .execute()
    )

    messages = results.get(
        "messages",
        []
    )

    emails = []

    for msg in messages:

        data = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=msg["id"],
                format="full"
            )
            .execute()
        )

        headers = (
            data.get(
                "payload",
                {}
            )
            .get(
                "headers",
                []
            )
        )

        header_map = {
            h["name"]: h["value"]
            for h in headers
        }

        payload = data.get("payload", {})

        full_body = extract_plain_text(payload)

        emails.append({

            "from":
                header_map.get(
                    "From",
                    ""
                ),

            "subject":
                header_map.get(
                    "Subject",
                    ""
                ),

            "date":
                header_map.get(
                    "Date",
                    ""
                ),

            "snippet":
                data.get(
                    "snippet",
                    ""
                ),

            "body":
                full_body[:12000]

        })

    return emails

# =====================================================
# GPT SUMMARY
# =====================================================

def summarize_emails(emails):

    if not emails:

        return (
            "No emails found."
        )

    email_text = ""

    for i, e in enumerate(
        emails,
        start=1
    ):

        email_text += f"""

EMAIL {i}

FROM:
{e['from']}

SUBJECT:
{e['subject']}

DATE:
{e['date']}

SNIPPET:
{e['snippet']}

FULL BODY:
{e['body']}

--------------------------------

"""

    prompt = f"""

You are Emily,
Doug's executive inbox assistant.

Your goals:
- reduce overwhelm
- identify true priorities
- summarize clearly
- explain important context
- ADHD friendly formatting
- separate noise from signal

Output format:

# Inbox Summary

## Top Priorities
- ...

## Important Context
- ...

## Action Items
- ...

## Low Priority / Noise
- ...

EMAIL DATA:

{email_text}

"""

    response = (
        client.chat.completions.create(

            model="gpt-4o-mini",

            messages=[

                {
                    "role": "system",
                    "content":
                    "You are a structured executive inbox assistant."
                },

                {
                    "role": "user",
                    "content": prompt
                }

            ],

            temperature=0.2

        )
    )

    return (
        response
        .choices[0]
        .message
        .content
    )

# =====================================================
# MAIN HANDLER
# =====================================================

def handle_email_request(message: str):

    try:

        emails = get_emails(8)

        summary = summarize_emails(
            emails
        )

        return summary

    except Exception as e:

        return f"""

Emily could not access Gmail.

Error:
{str(e)}

"""
