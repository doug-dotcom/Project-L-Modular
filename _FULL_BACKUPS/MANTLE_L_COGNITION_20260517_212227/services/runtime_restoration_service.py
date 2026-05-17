# =====================================================
# runtime_restoration_service.py
# AODS 86
# =====================================================

import json
import uuid
from pathlib import Path
from datetime import datetime

from services.runtime_snapshot_service import (
    latest_snapshot,
    recent_snapshots
)

RESTORE_DIR = Path("restore")

RESTORE_FILE = RESTORE_DIR / "restoration_log.json"

MAX_RESTORES = 250

def ensure_restore_store():

    RESTORE_DIR.mkdir(exist_ok=True)

    if not RESTORE_FILE.exists():

        with open(RESTORE_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)

def load_restore_log():

    ensure_restore_store()

    try:
        with open(RESTORE_FILE, "r", encoding="utf-8") as f:

            data = json.load(f)

        if isinstance(data, list):

            return data

        return []

    except Exception:

        return []

def save_restore_log(items):

    items = items[-MAX_RESTORES:]

    with open(RESTORE_FILE, "w", encoding="utf-8") as f:

        json.dump(items, f, indent=2)

def restore_latest_snapshot():

    snapshot = latest_snapshot()

    restore_event = {
        "restore_id": str(uuid.uuid4()),

        "timestamp": datetime.now().isoformat(),

        "restore_type": "latest_snapshot",

        "snapshot": snapshot,

        "status": (
            "restored"
            if snapshot.get("snapshot_status")
            else "failed"
        )
    }

    items = load_restore_log()

    items.append(restore_event)

    save_restore_log(items)

    return restore_event

def restore_by_label(label):

    snapshots = recent_snapshots(100)

    matched = None

    for snap in snapshots:

        if snap.get("label") == label:

            matched = snap
            break

    restore_event = {
        "restore_id": str(uuid.uuid4()),

        "timestamp": datetime.now().isoformat(),

        "restore_type": "label_restore",

        "requested_label": label,

        "snapshot": matched,

        "status": (
            "restored"
            if matched
            else "not_found"
        )
    }

    items = load_restore_log()

    items.append(restore_event)

    save_restore_log(items)

    return restore_event

def restoration_status():

    items = load_restore_log()

    restored = [
        i for i in items
        if i.get("status") == "restored"
    ]

    failed = [
        i for i in items
        if i.get("status") != "restored"
    ]

    return {
        "timestamp": datetime.now().isoformat(),

        "restore_operations": len(items),

        "successful_restores": len(restored),

        "failed_restores": len(failed),

        "status": "online"
    }

def recent_restorations(limit=10):

    return load_restore_log()[-limit:]

def restoration_summary():

    latest = (
        recent_restorations(1)[0]
        if recent_restorations(1)
        else {}
    )

    return {
        "timestamp": datetime.now().isoformat(),

        "latest_restore": latest.get(
            "restore_type"
        ),

        "latest_status": latest.get(
            "status"
        ),

        "status": "summary_ready"
    }
