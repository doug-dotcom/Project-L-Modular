# =====================================================
# workflow_chain_service.py
# AODS 58
# =====================================================

import json
from pathlib import Path
from datetime import datetime
from services.runtime_state_service import increment_workflows, update_runtime_event

WORKFLOW_FILE = Path("workflows") / "workflow_chains.json"

DEFAULT_CHAIN = [
    "triage",
    "response_prepare",
    "reply"
]

def load_workflows():

    try:
        with open(WORKFLOW_FILE, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return {
            "chains": {
                "general_chain": DEFAULT_CHAIN
            }
        }

def get_chain(chain_name):

    workflows = load_workflows()

    chains = workflows.get("chains", {})

    return chains.get(chain_name, DEFAULT_CHAIN)

def category_to_chain(category):

    mapping = {
        "memory": "memory_chain",
        "care": "care_chain",
        "build": "build_chain",
        "email": "email_chain",
        "calendar": "calendar_chain",
        "general": "general_chain"
    }

    return mapping.get(category, "general_chain")

def execute_chain(category, payload):

    increment_workflows()

    update_runtime_event(f"workflow:{category}")

    chain_name = category_to_chain(category)

    steps = get_chain(chain_name)

    execution_log = []

    for step in steps:

        execution_log.append({
            "step": step,
            "status": "complete",
            "timestamp": datetime.now().isoformat()
        })

    return {
        "chain": chain_name,
        "steps": execution_log,
        "payload": payload,
        "status": "complete"
    }

