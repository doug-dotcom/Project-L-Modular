from api.google_auth import (
    get_google_service
)

# =====================================================
# ROUTING
# =====================================================

def should_handle(message: str) -> bool:

    text = message.lower()

    triggers = [

        "task",
        "tasks",
        "todo",
        "to do",
        "reminder",
        "reminders"

    ]

    return any(
        t in text
        for t in triggers
    )

# =====================================================
# NAME-ONLY INTERACTION
# =====================================================

def handle_name_only():

    return """

# ✅ Tania

Would you like me to:

1. Check your tasks
2. Create a new task
3. Review priorities
4. Something else

"""

# =====================================================
# GET TASKS
# =====================================================

def get_tasks():

    service = get_google_service(
        "tasks",
        "v1"
    )

    tasklists = (
        service.tasklists()
        .list()
        .execute()
    )

    lists = tasklists.get(
        "items",
        []
    )

    all_tasks = []

    for tasklist in lists:

        tasks = (
            service.tasks()
            .list(
                tasklist=tasklist["id"]
            )
            .execute()
        )

        items = tasks.get(
            "items",
            []
        )

        for t in items:

            all_tasks.append({

                "title":
                    t.get(
                        "title",
                        "Untitled"
                    ),

                "status":
                    t.get(
                        "status",
                        "unknown"
                    )

            })

    return all_tasks

# =====================================================
# FORMAT TASKS
# =====================================================

def summarize_tasks(tasks):

    if not tasks:

        return """

# ✅ Tania Tasks

No active tasks found.

"""

    output = """

# ✅ Tania Tasks

## 👀 Current Tasks

"""

    for t in tasks:

        output += f"""

- {t['title']}
  → {t['status']}

"""

    return output

# =====================================================
# CREATE TASK
# =====================================================

def create_task_from_handoff(task_data):

    try:

        service = get_google_service(
            "tasks",
            "v1"
        )

        tasklists = (
            service.tasklists()
            .list()
            .execute()
        )

        lists = tasklists.get(
            "items",
            []
        )

        if not lists:

            return "❌ No task lists found."

        primary = lists[0]["id"]

        body = {

            "title":
                task_data.get(
                    "subject",
                    "Task"
                ),

            "notes":
                task_data.get(
                    "snippet",
                    ""
                )

        }

        service.tasks().insert(
            tasklist=primary,
            body=body
        ).execute()

        return f"""

# ✅ Tania

Task created successfully.

🧠 Created Task:
{body['title']}

"""

    except Exception as e:

        return f"""

# ❌ Tania

Task creation failed.

Error:
{str(e)}

"""

# =====================================================
# MAIN HANDLER
# =====================================================

def handle_task_request(message: str):

    text = message.lower().strip()

    # =================================================
    # NAME ONLY
    # =================================================

    if text == "tania":

        return handle_name_only()

    # =================================================
    # CHECK TASKS
    # =================================================

    if any(
        p in text
        for p in [

            "check tasks",
            "show tasks",
            "my tasks",
            "task list"

        ]
    ):

        tasks = get_tasks()

        return summarize_tasks(tasks)

    # =================================================
    # FALLBACK
    # =================================================

    return """

# ✅ Tania

I can help with:

- task management
- reminders
- priorities
- execution support

What would you like to do?

"""
