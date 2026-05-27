def should_handle(message: str) -> bool:

    text = (message or "").lower()

    triggers = [

        "task",
        "todo",
        "to do",
        "action item",
        "tanya",
        "tania"

    ]

    return any(
        t in text
        for t in triggers
    )

def handle_task_request(message: str):

    return """

# ✅ Tanya Tasks

Execution layer online.

Ready for:
- task capture
- action items
- Google Tasks integration
- operational execution

"""

