# =====================================================
# runtime_completion_seal_service.py
# AODS 90
# =====================================================

import json
import uuid
from pathlib import Path
from datetime import datetime

from services.runtime_integration_spine_service import (
    spine_summary,
    spine_health
)

from services.runtime_finalisation_service import (
    finalisation_status,
    finalisation_brief
)

from services.runtime_continuity_service import (
    continuity_summary
)

from services.runtime_deployment_readiness_service import (
    deployment_recommendation
)

SEAL_DIR = Path("seal")

SEAL_FILE = SEAL_DIR / "runtime_completion_seal.json"

def ensure_seal_store():

    SEAL_DIR.mkdir(exist_ok=True)

    if not SEAL_FILE.exists():

        with open(SEAL_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=2)

def save_seal(data):

    ensure_seal_store()

    with open(SEAL_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_seal():

    ensure_seal_store()

    try:
        with open(SEAL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return {}

def create_completion_seal():

    spine = spine_summary()
    health = spine_health()
    finalisation = finalisation_status()
    continuity = continuity_summary()
    deployment = deployment_recommendation()
    brief = finalisation_brief()

    seal = {
        "seal_id": str(uuid.uuid4()),

        "timestamp": datetime.now().isoformat(),

        "project": "Project L",

        "stage": "Stage 3",

        "completion": "AODS 90",

        "runtime_state": "CANONICAL",

        "spine_summary": spine,

        "spine_health": health,

        "finalisation": finalisation,

        "continuity": continuity,

        "deployment": deployment,

        "finalisation_brief": brief,

        "completion_message": (
            "Stage 3 runtime architecture sealed successfully."
        ),

        "status": "SEALED"
    }

    save_seal(seal)

    return seal

def completion_seal_status():

    seal = load_seal()

    return {
        "timestamp": datetime.now().isoformat(),

        "sealed": bool(seal),

        "project": seal.get("project"),

        "stage": seal.get("stage"),

        "completion": seal.get("completion"),

        "status": seal.get("status", "UNSEALED")
    }

def completion_summary():

    seal = load_seal()

    return {
        "timestamp": datetime.now().isoformat(),

        "project": seal.get("project"),

        "completion": seal.get("completion"),

        "runtime_state": seal.get("runtime_state"),

        "completion_message": seal.get(
            "completion_message"
        ),

        "status": seal.get("status")
    }

def operator_completion_brief():

    summary = completion_summary()

    return {
        "timestamp": datetime.now().isoformat(),

        "summary": summary,

        "operator_message": (
            "Runtime architecture stable. "
            "Canonical Stage 3 operational baseline established."
        )
    }
