from openai import OpenAI

client = OpenAI()

# =====================================================
# EMILY ROUTING
# =====================================================

def should_handle(message: str) -> bool:

    text = message.lower()

    triggers = [

        "email",
        "emails",
        "inbox",
        "gmail",
        "check my email",
        "summarize my inbox",
        "summarise my inbox",
        "important emails",
        "priority emails",
        "emily"

    ]

    return any(
        t in text
        for t in triggers
    )

# =====================================================
# PLACEHOLDER SUMMARY
# =====================================================

def summarize_inbox():

    return """

# 📧 Emily Email Summary

## 🔥 Top Priorities

1. Follow up on important financial emails.
2. Review any DVA-related communication.
3. Check appointment confirmations.

---

## 🧠 Suggested Actions

- Clear low-priority inbox clutter.
- Reply to urgent personal messages.
- Flag important follow-ups.

---

## 👀 Notes

This is Emily Email V1.
Live Gmail integration already exists and will be connected next.

"""

# =====================================================
# MAIN EMILY HANDLER
# =====================================================

def handle_email_request(message: str):

    return summarize_inbox()
