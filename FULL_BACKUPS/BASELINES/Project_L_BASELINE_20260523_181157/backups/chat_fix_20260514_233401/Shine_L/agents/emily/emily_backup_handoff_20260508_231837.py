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
                format="metadata",
                metadataHeaders=[
                    "From",
                    "Subject",
                    "Date"
                ]
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
                )
        })

    return emails

# =====================================================
# GPT SUMMARY
# =====================================================

def summarize_emails(emails):

    if not emails:

        return """

# 📧 Emily Email

No emails found in inbox.

"""

    email_text = ""

    for i, e in enumerate(
        emails,
        start=1
    ):

        email_text += f"""

EMAIL {i}

From:
{e['from']}

Subject:
{e['subject']}

Date:
{e['date']}

Snippet:
{e['snippet']}

---
"""

    prompt = f"""

You are Emily Email,
Doug's inbox assistant.

Your job:
- identify important emails
- reduce overwhelm
- separate signal from noise
- summarize clearly
- ADHD friendly formatting

Output format:

# 📧 Emily Email Summary

## 🔥 Top Priorities

- ...

## 👀 Inbox Overview

- ...

## ✅ Suggested Actions

- ...

EMAILS:

{email_text}

"""

    response = (
        client.chat.completions.create(

            model="gpt-4o-mini",

            messages=[

                {
                    "role":"system",
                    "content":
                    "You are a structured inbox assistant."
                },

                {
                    "role":"user",
                    "content":prompt
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

        emails = get_emails(5)

        return summarize_emails(
            emails
        )

    except Exception as e:

        return f"""

# 📧 Emily Email

## ❌ Gmail Connection Error

Emily could not access Gmail.

Error:
{str(e)}

"""
