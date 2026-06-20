from api.google_auth import (
    get_google_service
)

# =====================================================
# EMILY V3
# EMAIL ASSISTANT
# =====================================================

def should_handle(message: str) -> bool:

    text = (message or "").lower()

    triggers = [

        "check my emails",
        "check my email",
        "look at my emails",
        "look at my email",
        "get my emails",
        "get my email",
        "review my emails",
        "review my email",
        "email summary",
        "inbox summary",
        "gmail summary",
        "check gmail",
        "open inbox",
        "read my emails",
        "latest emails",
        "latest email"

    ]

    return any(
        t in text
        for t in triggers
    )

# =====================================================
# EMAIL RETRIEVAL
# =====================================================

def get_emails():

    service = get_google_service(
        "gmail",
        "v1"
    )

    results = (
        service.users()
        .messages()
        .list(
            userId="me",
            q="in:inbox newer_than:30d",
            maxResults=20
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
                id=msg["id"]
            )
            .execute()
        )

        headers = (
            data.get("payload", {})
            .get("headers", [])
        )

        sender = ""
        subject = ""
        date = ""

        for h in headers:

            name = h.get("name", "").lower()

            if name == "from":
                sender = h.get("value", "")

            elif name == "subject":
                subject = h.get("value", "")

            elif name == "date":
                date = h.get("value", "")

        emails.append({

            "from": sender,
            "subject": subject,
            "date": date,
            "snippet": data.get("snippet", ""),

            "timestamp":
                int(
                    data.get(
                        "internalDate",
                        0
                    )
                )

        })

    # =================================================
    # SORT NEWEST FIRST
    # =================================================

    emails.sort(
        key=lambda x: x["timestamp"],
        reverse=True
    )

    return emails

# =====================================================
# OUTPUT
# =====================================================

def handle_email_request(message: str):

    try:

        emails = get_emails()

        output = "# 📧 Emily Inbox Summary\n\n"

        if not emails:

            output += "No emails found."

            return output

        for idx, email in enumerate(emails):

            output += (
                f"{idx+1}.\n\n"
                f"FROM: {email['from']}\n"
                f"SUBJECT: {email['subject']}\n"
                f"DATE: {email['date']}\n"
                f"SNIPPET: {email['snippet']}\n\n"
            )

        return output

    except Exception as e:

        return f"""

# 📧 Emily Error

{str(e)}

IMPORTANT:
You probably need:
- credentials.json
- first-time Google login

"""

