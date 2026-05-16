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
        "reminders",
        "check my tasks",
        "show my tasks",
        "tania"

    ]

    return any(
        t in text
        for t in triggers
    )

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
# MAIN HANDLER
# =====================================================

def handle_task_request(message: str):

    try:

        tasks = get_tasks()

        return summarize_tasks(
            tasks
        )

    except Exception as e:

        return f"""

# ✅ Tania Tasks

## ❌ Task Error

{str(e)}

"""

# =====================================================
# CREATE TASK FROM HANDOFF
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

        return f"✅ Task created: {body['title']}"

    except Exception as e:

        return f"❌ Task creation failed: {str(e)}"

