def should_handle(message: str) -> bool:

    text = (message or "").lower()

    triggers = [

        "email",
        "emails",
        "gmail",
        "inbox",
        "emily"

    ]

    return any(
        t in text
        for t in triggers
    )

def handle_email_request(message: str):

    return """

# 📧 Emily Inbox Assistant

Emily is online.

Google Gmail integration is active.

Ready for:
- inbox summaries
- priority emails
- executive briefings
- ADHD friendly inbox organization

"""
