# =====================================================
# runtime_finalisation_service.py
# AODS 89
# =====================================================

import json
from pathlib import Path
from datetime import datetime

from services.runtime_operator_interface_service import operator_brief
from services.runtime_snapshot_service import create_snapshot, snapshot_summary
from services.runtime_deployment_readiness_service import deployment_recommendation
from services.runtime_continuity_service import continuity_summary
from services.runtime_lock_service import runtime_permitted

FINAL_DIR = Path("finalisation")
FINAL_FILE = FINAL_DIR / "runtime_finalisation.json"

def ensure_final_store():

    FINAL_DIR.mkdir(exist_ok=True)

    if not FINAL_FILE.exists():

        with open(FINAL_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=2)

def save_finalisation(data):

    ensure_final_store()

    with open(FINAL_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_finalisation():

    ensure_final_store()

    try:
        with open(FINAL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return {}

def finalisation_check():

    deployment = deployment_recommendation()
    continuity = continuity_summary()
    permitted = runtime_permitted()
    operator = operator_brief()

    ready = (
        permitted.get("runtime_permitted") is True
        and continuity.get("continuity_valid") is True
    )

    return {
        "timestamp": datetime.now().isoformat(),
        "ready_for_finalisation": ready,
        "deployment": deployment,
        "continuity": continuity,
        "runtime_permission": permitted,
        "operator": operator
    }

def create_finalisation_record(label="AODS89_FINALISATION"):

    check = finalisation_check()

    snapshot = create_snapshot(label=label)

    record = {
        "timestamp": datetime.now().isoformat(),
        "label": label,
        "stage": "Stage 3",
        "aods": 89,
        "finalisation_ready": check.get("ready_for_finalisation"),
        "final_snapshot": snapshot,
        "check": check,
        "status": "finalisation_recorded"
    }

    save_finalisation(record)

    return record

def finalisation_status():

    data = load_finalisation()

    return {
        "timestamp": datetime.now().isoformat(),
        "finalisation_exists": bool(data),
        "label": data.get("label"),
        "aods": data.get("aods"),
        "status": data.get("status", "not_finalised"),
        "snapshot": snapshot_summary()
    }

def finalisation_brief():

    return {
        "timestamp": datetime.now().isoformat(),
        "status": finalisation_status(),
        "check": finalisation_check()
    }
