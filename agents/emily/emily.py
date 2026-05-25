from api.google_auth import (
    get_google_service
)

def should_handle(message: str) -> bool:

    text = (message or "").lower()

    triggers = [

        "email",
        "emails",
        "gmail",
        "inbox",
        "emily",
        "check my emails",
        "check my email"

    ]

    return any(
        t in text
        for t in triggers
    )

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
            maxResults=5
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

        emails.append({

            "snippet":
                data.get(
                    "snippet",
                    ""
                )

        })

    return emails

def handle_email_request(message: str):

    try:

        emails = get_emails()

        output = "# 📧 Emily Inbox Summary\n\n"

        if not emails:

            output += "No emails found."

            return output

        for idx, email in enumerate(emails):

            output += (
                f"{idx+1}. "
                + email["snippet"]
                + "\n\n"
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
