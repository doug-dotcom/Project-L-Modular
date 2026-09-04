"""Neutral Gmail, Calendar and Tasks capability adapters for L."""

from __future__ import annotations

import re
from datetime import datetime, timezone


EMAIL_TRIGGERS = (
    "check my email", "check my emails", "look at my email", "look at my emails",
    "get my email", "get my emails", "review my email", "review my emails",
    "email summary", "inbox summary", "gmail summary", "check gmail", "open inbox",
    "read my emails", "latest email", "latest emails",
)
CALENDAR_TRIGGERS = ("calendar", "what is on today", "what's on today")
TASK_TRIGGERS = (
    "action item", "add to tasks", "add to my tasks", "add to do",
    "add to my to do list", "what is on my task list", "what tasks do i have",
    "recall my tasks", "show my tasks", "my tasks",
)


def classify_google_capability(message: str) -> str:
    text = str(message or "").lower()
    if any(trigger in text for trigger in EMAIL_TRIGGERS):
        return "gmail"
    if any(trigger in text for trigger in CALENDAR_TRIGGERS):
        return "calendar"
    if any(trigger in text for trigger in TASK_TRIGGERS):
        return "tasks"
    return ""


def _google_service(name: str, version: str):
    from api.google_auth import get_google_service
    return get_google_service(name, version)


def gmail_summary(_message: str, limit: int = 20) -> str:
    service = _google_service("gmail", "v1")
    found = service.users().messages().list(
        userId="me", q="in:inbox newer_than:30d", maxResults=limit
    ).execute().get("messages", [])
    rows = []
    for reference in found:
        data = service.users().messages().get(
            userId="me", id=reference["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date"],
        ).execute()
        headers = {
            item.get("name", "").lower(): item.get("value", "")
            for item in data.get("payload", {}).get("headers", [])
        }
        rows.append({
            "from": headers.get("from", ""),
            "subject": headers.get("subject", ""),
            "date": headers.get("date", ""),
            "snippet": data.get("snippet", ""),
        })
    if not rows:
        return "Gmail service returned no inbox messages from the past 30 days."
    lines = ["Gmail service result:"]
    for index, row in enumerate(rows, 1):
        lines.append(
            f"{index}. From: {row['from']} | Subject: {row['subject']} | "
            f"Date: {row['date']} | Snippet: {row['snippet']}"
        )
    return "\n".join(lines)[:12000]


def calendar_summary(_message: str, limit: int = 10) -> str:
    service = _google_service("calendar", "v3")
    events = service.events().list(
        calendarId="primary",
        timeMin=datetime.now(timezone.utc).isoformat(),
        maxResults=limit,
        singleEvents=True,
        orderBy="startTime",
    ).execute().get("items", [])
    if not events:
        return "Calendar service returned no upcoming events."
    lines = ["Calendar service result:"]
    for event in events:
        start = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date", "")
        lines.append(f"- {event.get('summary', 'Untitled')} | {start}")
    return "\n".join(lines)[:8000]


def _task_title(message: str) -> str:
    text = str(message or "").strip()
    match = re.search(
        r"(?:add to (?:my )?(?:tasks?|to do list)|action item)\s*[:\-]?\s*(.+)$",
        text,
        re.I,
    )
    return (match.group(1) if match else "").strip()[:500]


def tasks_result(message: str, limit: int = 20) -> str:
    service = _google_service("tasks", "v1")
    tasklists = service.tasklists().list(maxResults=1).execute().get("items", [])
    if not tasklists:
        return "Tasks service found no task list and made no change."
    tasklist_id = tasklists[0]["id"]
    title = _task_title(message)
    if title:
        created = service.tasks().insert(tasklist=tasklist_id, body={"title": title}).execute()
        return f"Tasks service created: {created.get('title', title)}."
    tasks = service.tasks().list(
        tasklist=tasklist_id, maxResults=limit, showCompleted=False
    ).execute().get("items", [])
    if not tasks:
        return "Tasks service returned no incomplete tasks."
    return "Tasks service result:\n" + "\n".join(
        f"- {task.get('title', 'Untitled')}" for task in tasks
    )
