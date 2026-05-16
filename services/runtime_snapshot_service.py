# =====================================================
# runtime_snapshot_service.py
# AODS 85
# =====================================================

import json
import uuid
from pathlib import Path
from datetime import datetime

from services.runtime_integration_spine_service import (
    integration_spine,
    spine_summary
)

from services.runtime_release_candidate_service import (
    latest_candidate
)

SNAP_DIR = Path("snapshots")

SNAP_FILE = SNAP_DIR / "canonical_snapshots.json"

MAX_SNAPSHOTS = 250

def ensure_snapshot_store():

    SNAP_DIR.mkdir(exist_ok=True)

    if not SNAP_FILE.exists():

        with open(SNAP_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)

def load_snapshots():

    ensure_snapshot_store()

    try:
        with open(SNAP_FILE, "r", encoding="utf-8") as f:

            data = json.load(f)

        if isinstance(data, list):

            return data

        return []

    except Exception:

        return []

def save_snapshots(items):

    items = items[-MAX_SNAPSHOTS:]

    with open(SNAP_FILE, "w", encoding="utf-8") as f:

        json.dump(items, f, indent=2)

def create_snapshot(label="canonical_snapshot"):

    spine = integration_spine()

    summary = spine_summary()

    rc = latest_candidate()

    snapshot = {
        "snapshot_id": str(uuid.uuid4()),

        "timestamp": datetime.now().isoformat(),

        "label": label,

        "spine_summary": summary,

        "release_candidate": rc,

        "runtime_spine": spine,

        "snapshot_status": "canonical"
    }

    items = load_snapshots()

    items.append(snapshot)

    save_snapshots(items)

    return snapshot

def snapshot_status():

    items = load_snapshots()

    return {
        "timestamp": datetime.now().isoformat(),

        "snapshot_count": len(items),

        "latest_snapshot": (
            items[-1]["label"]
            if items else None
        ),

        "status": "online"
    }

def recent_snapshots(limit=10):

    return load_snapshots()[-limit:]

def latest_snapshot():

    items = load_snapshots()

    if not items:

        return {
            "status": "no_snapshots"
        }

    return items[-1]

def snapshot_summary():

    latest = latest_snapshot()

    return {
        "timestamp": datetime.now().isoformat(),

        "latest_snapshot": latest.get(
            "label"
        ),

        "snapshot_status": latest.get(
            "snapshot_status"
        ),

        "release_candidate": latest.get(
            "release_candidate",
            {}
        ).get(
            "label"
        ),

        "status": "summary_ready"
    }
