# =====================================================
# runtime_release_candidate_service.py
# AODS 84
# =====================================================

import json
import uuid
from pathlib import Path
from datetime import datetime

from services.runtime_deployment_readiness_service import (
    deployment_checks
)

from services.runtime_integration_spine_service import (
    spine_summary
)

RC_DIR = Path("release_candidates")

RC_FILE = RC_DIR / "runtime_release_candidates.json"

MAX_RC = 250

def ensure_rc_store():

    RC_DIR.mkdir(exist_ok=True)

    if not RC_FILE.exists():

        with open(RC_FILE, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)

def load_candidates():

    ensure_rc_store()

    try:
        with open(RC_FILE, "r", encoding="utf-8") as f:

            data = json.load(f)

        if isinstance(data, list):

            return data

        return []

    except Exception:

        return []

def save_candidates(items):

    items = items[-MAX_RC:]

    with open(RC_FILE, "w", encoding="utf-8") as f:

        json.dump(items, f, indent=2)

def create_release_candidate(label="runtime_rc"):

    readiness = deployment_checks()

    spine = spine_summary()

    candidate = {
        "candidate_id": str(uuid.uuid4()),

        "timestamp": datetime.now().isoformat(),

        "label": label,

        "deployment_ready": readiness.get(
            "ready_for_deployment",
            False
        ),

        "spine_summary": spine,

        "deployment_checks": readiness,

        "approval_status": (
            "candidate_ready"
            if readiness.get(
                "ready_for_deployment",
                False
            )
            else "candidate_blocked"
        )
    }

    items = load_candidates()

    items.append(candidate)

    save_candidates(items)

    return candidate

def candidate_status():

    items = load_candidates()

    ready = [
        i for i in items
        if i.get("deployment_ready")
    ]

    blocked = [
        i for i in items
        if not i.get("deployment_ready")
    ]

    return {
        "timestamp": datetime.now().isoformat(),

        "candidate_count": len(items),

        "ready_candidates": len(ready),

        "blocked_candidates": len(blocked),

        "status": "online"
    }

def recent_candidates(limit=10):

    return load_candidates()[-limit:]

def latest_candidate():

    items = load_candidates()

    if not items:

        return {
            "status": "no_candidates"
        }

    return items[-1]

def candidate_summary():

    latest = latest_candidate()

    return {
        "timestamp": datetime.now().isoformat(),

        "latest_candidate": latest.get(
            "label"
        ),

        "approval_status": latest.get(
            "approval_status"
        ),

        "deployment_ready": latest.get(
            "deployment_ready"
        ),

        "status": "summary_ready"
    }
