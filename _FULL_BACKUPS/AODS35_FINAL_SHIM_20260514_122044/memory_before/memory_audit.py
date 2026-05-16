import json
import os
from datetime import datetime

from core.json_store import (
    safe_load_json,
    safe_save_json,
)

from core.paths import (
    MEMORY_AUDIT_FILE,
)

from core.paths import ROOT


def audit_memory_event(
    event_type,
    target,
    details=None
):

    try:

        audit = safe_load_json(
            MEMORY_AUDIT_FILE,
            []
        )

        audit.append({

            "timestamp": str(datetime.now()),

            "event_type": event_type,

            "target": target,

            "details": details or {}

        })

        safe_save_json(
            MEMORY_AUDIT_FILE,
            audit
        )

    except Exception as e:

        print(
            "MEMORY AUDIT ERROR:",
            e
        )


def memory_file_status():

    files = [

        "memory/conversations.json",

        "memory/life_story.json",

        "memory/profile.json",

        "memory/invisible_orchestra_log.json",

        "memory/memory_audit.json"

    ]

    results = []

    for path in files:

        full_path = ROOT / path

        item = {

            "file": path,

            "exists": os.path.exists(full_path),

            "size_bytes": 0,

            "last_modified": None,

            "entries": None

        }

        if os.path.exists(full_path):

            item["size_bytes"] = os.path.getsize(full_path)

            item["last_modified"] = str(
                datetime.fromtimestamp(
                    os.path.getmtime(full_path)
                )
            )

            try:

                data = safe_load_json(full_path, None)

                if isinstance(data, list):

                    item["entries"] = len(data)

                elif isinstance(data, dict):

                    item["entries"] = len(data.keys())

            except:

                item["entries"] = "unknown"

        results.append(item)

    return results


def build_memory_audit_report():

    audit = safe_load_json(
        MEMORY_AUDIT_FILE,
        []
    )

    recent = audit[-10:]

    report = {

        "memory_files": memory_file_status(),

        "recent_events": recent

    }

    return report


def hard_memory_audit_v2():

    files = [
        "memory/profile.json",
        "memory/conversations.json",
        "memory/life_story.json",
        "memory/invisible_orchestra_log.json",
        "memory/memory_audit.json"
    ]

    report = []

    known_identity = {
        "user_name": "Doug Struthers",
        "not_user_name": "Tamara",
        "children": ["Iyla", "Ashton", "Luella", "Mehlia"],
        "identity_confidence": "high",
        "source": "hard identity guard"
    }

    for path in files:

        full_path = ROOT / path

        item = {
            "source_file": path,
            "exists": os.path.exists(full_path),
            "entries": 0,
            "size_bytes": 0,
            "last_modified": None,
            "notes": []
        }

        if os.path.exists(full_path):

            item["size_bytes"] = os.path.getsize(full_path)

            item["last_modified"] = str(
                datetime.fromtimestamp(
                    os.path.getmtime(full_path)
                )
            )

            data = safe_load_json(full_path, None)

            if isinstance(data, list):

                item["entries"] = len(data)

            elif isinstance(data, dict):

                item["entries"] = len(data.keys())

            blob = (
                json.dumps(
                    data,
                    ensure_ascii=False
                ).lower()
                if data else ""
            )

            if "your name is tamara" in blob:

                item["notes"].append(
                    "WARNING: possible identity contamination phrase found"
                )

            if "tamara" in blob:

                item["notes"].append(
                    "Tamara appears in this file; treat as relationship context, not user identity"
                )

            if "doug" in blob or "struthers" in blob:

                item["notes"].append(
                    "Doug identity reference found"
                )

        report.append(item)

    return {
        "audit_version": "Memory Audit V2",
        "identity_guard": known_identity,
        "memory_files": report,
        "rule": "Do not infer user identity from relationship memories. Doug Struthers is the user. Tamara is not the user.",
        "instruction": "If recall is uncertain, state the source file and confidence rather than guessing."
    }


def format_hard_memory_audit_v2():

    audit = hard_memory_audit_v2()

    lines = []

    lines.append("MEMORY AUDIT V2 — SOURCE ATTRIBUTION")

    lines.append("")

    lines.append("IDENTITY GUARD")

    lines.append("User: Doug Struthers")

    lines.append("Not user: Tamara")

    lines.append("Children: Iyla, Ashton, Luella, Mehlia")

    lines.append("Confidence: high")

    lines.append("")

    lines.append("MEMORY FILES")

    for item in audit["memory_files"]:

        lines.append("")

        lines.append("- " + item["source_file"])

        lines.append("  exists: " + str(item["exists"]))

        lines.append("  entries: " + str(item["entries"]))

        lines.append("  size_bytes: " + str(item["size_bytes"]))

        lines.append("  last_modified: " + str(item["last_modified"]))

        if item["notes"]:

            lines.append("  notes:")

            for note in item["notes"]:

                lines.append("    - " + note)

    lines.append("")

    lines.append("RULE")

    lines.append("Do not infer Doug's identity from relationship memories.")

    lines.append("Tamara may appear in memories, but Tamara is not the user.")

    lines.append("")

    lines.append("If memory recall is uncertain, say which file was searched and what confidence level was found.")

    return "\n".join(lines)
