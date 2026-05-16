import json
from pathlib import Path
from datetime import datetime

from core.json_store import (
    safe_load_json,
    safe_save_json,
)

ROOT = Path(r"C:\Shine_L")
CAPTAINS_DIR = ROOT / "memory" / "captains"
LOCAL_JSON_DIR = ROOT / "memory" / "local_json"
EVENT_STREAM = LOCAL_JSON_DIR / "runtime_event_stream.json"
RUNTIME_STATUS = ROOT / "memory" / "indexes" / "runtime_cutover_status.json"

try:
    from memory.memory_engine import (
        process as legacy_process,
        build_context as legacy_build_context,
    )
except Exception as e:
    print("LEGACY MEMORY ENGINE IMPORT ERROR:", e)
    legacy_process = None
    legacy_build_context = None


def collect_local_captain_memories(limit_per_file=20):

    memories = []

    for file in CAPTAINS_DIR.rglob("*.json"):

        data = safe_load_json(file, {})

        entries = data.get("entries", [])

        for item in entries[:limit_per_file]:

            content = (
                item.get("content")
                or item.get("text")
                or item.get("memory")
                or item.get("value")
                or str(item)
            )

            memories.append({
                "source_file": str(file),
                "content": content
            })

    return memories


def build_local_context():

    memories = collect_local_captain_memories()

    if not memories:

        return ""

    lines = []
    lines.append("\n\nLOCAL JSON MEMORY CONTEXT:")
    lines.append("Runtime source: PCG local captain JSON")
    lines.append("Supabase role: protected backup / sync layer")
    lines.append("")

    for item in memories[:80]:

        lines.append("- " + str(item.get("content", ""))[:500])

    return "\n".join(lines)


def process(user_msg):

    LOCAL_JSON_DIR.mkdir(parents=True, exist_ok=True)

    events = safe_load_json(EVENT_STREAM, [])

    events.append({
        "timestamp": datetime.now().isoformat(),
        "type": "user_message",
        "message": user_msg,
        "runtime": "local_json_first"
    })

    safe_save_json(EVENT_STREAM, events)

    if legacy_process:

        try:
            legacy_process(user_msg)
        except Exception as e:
            print("LEGACY PROCESS FALLBACK ERROR:", e)


def build_context():

    local_context = build_local_context()

    legacy_context = ""

    if legacy_build_context:

        try:
            legacy_context = legacy_build_context()
        except Exception as e:
            print("LEGACY BUILD CONTEXT FALLBACK ERROR:", e)

    return (
        local_context
        + "\n\n"
        + legacy_context
    ).strip()


def runtime_status():

    return {
        "runtime": "local_json_first",
        "supabase": "backup_sync_layer",
        "runtime_cutover_complete": True,
        "supabase_modified": False,
        "created_by": "AODS34"
    }
