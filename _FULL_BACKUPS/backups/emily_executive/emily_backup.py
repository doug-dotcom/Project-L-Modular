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

# =====================================================
# LABEL LOOKUP
# =====================================================

def get_gmail_labels(service):

    labels = (
        service.users()
        .labels()
        .list(userId="me")
        .execute()
    )

    output = {}

    for label in labels.get("labels", []):

        output[
            label["name"]
        ] = label["id"]

    return output

# =====================================================
# APPLY LABEL
# =====================================================

def apply_label(service, msg_id, label_id):

    try:

        service.users().messages().modify(

            userId="me",

            id=msg_id,

            body={
                "addLabelIds": [label_id]
            }

        ).execute()

        return True

    except Exception as e:

        print("LABEL ERROR:", e)

        return False

# =====================================================
# REMOVE INBOX
# =====================================================

def remove_from_inbox(service, msg_id):

    try:

        service.users().messages().modify(

            userId="me",

            id=msg_id,

            body={
                "removeLabelIds": ["INBOX"]
            }

        ).execute()

    except Exception as e:

        print("REMOVE INBOX ERROR:", e)

# =====================================================
# TRIAGE CLASSIFIER
# =====================================================

def classify_email(email):

    text = (
        email.get("subject","")
        + " "
        + email.get("snippet","")
        + " "
        + email.get("body","")
    ).lower()

    # ================================================
    # ACTIONABLE
    # ================================================

    action_words = [

        "action required",
        "please respond",
        "deadline",
        "appointment",
        "meeting",
        "legal",
        "review request",
        "invoice",
        "payment due",
        "urgent",
        "follow up",
        "dva",
        "zurich",
        "claim",
        "school",
        "form",
        "assessment"

    ]

    # ================================================
    # REVIEW
    # ================================================

    review_words = [

        "newsletter",
        "update",
        "announcement",
        "community",
        "weekly",
        "digest",
        "report",
        "summary"

    ]

    # ================================================
    # NOISE
    # ================================================

    noise_words = [

        "sale",
        "offer",
        "discount",
        "promotion",
        "deal",
        "subscribe",
        "gift",
        "advertisement",
        "marketing",
        "last chance"

    ]

    if any(w in text for w in action_words):

        return "action"

    if any(w in text for w in review_words):

        return "review"

    if any(w in text for w in noise_words):

        return "noise"

    return "review"

# =====================================================
# AUTO TRIAGE
# =====================================================

def auto_triage_emails(emails):

    service = get_google_service(
        "gmail",
        "v1"
    )

    labels = get_gmail_labels(service)

    stats = {

        "action": 0,
        "review": 0,
        "noise": 0

    }

    for email in emails:

        msg_id = email.get("id")

        category = classify_email(email)

        # ============================================
        # ACTION
        # ============================================

        if category == "action":

            label = labels.get(
                "Inbox/Action"
            )

            if label:

                apply_label(
                    service,
                    msg_id,
                    label
                )

            stats["action"] += 1

        # ============================================
        # REVIEW
        # ============================================

        elif category == "review":

            label = labels.get(
                "Emily Review"
            )

            if label:

                apply_label(
                    service,
                    msg_id,
                    label
                )

            remove_from_inbox(
                service,
                msg_id
            )

            stats["review"] += 1

        # ============================================
        # NOISE
        # ============================================

        elif category == "noise":

            label = labels.get(
                "Emily Email"
            )

            if label:

                apply_label(
                    service,
                    msg_id,
                    label
                )

            remove_from_inbox(
                service,
                msg_id
            )

            stats["noise"] += 1

    return stats

