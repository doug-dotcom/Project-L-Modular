def should_handle(message: str) -> bool:

    text = (message or "").lower()

    triggers = [

      "tanya",
      "tania",

      "action item",

      "add to tasks",
      "add to my tasks",

      "add to do",
      "add to my to do list",

      "what is on my task list",
      "what tasks do i have",

      "recall my tasks",
      "show my tasks",
      "my tasks"

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
