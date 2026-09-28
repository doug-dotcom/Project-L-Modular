"""Bounded Shine AI planner for Concierge specialist orchestration.

The model may choose relevant live Foundation capability IDs. It cannot invent
capabilities, construct specialist payloads, grant permission, call specialists,
or override Foundation runtime state. Specialist inputs are compiled afterwards
from explicit user text by Layer 185's deterministic contract compiler.
"""

from __future__ import annotations

import json
from hashlib import sha256

from core.cognition.model_independence import build_model_request, invoke_model
from services.concierge_specialist_inputs import compile_specialist_input


MAX_SPECIALISTS = 4
MAX_CONTEXT_CHARS = 4000
MAX_MESSAGE_CHARS = 6000


def _catalogue(fleet: dict | None) -> list[dict]:
    specialists = (fleet or {}).get("specialists")
    if not isinstance(specialists, list):
        return []
    rows = []
    seen = set()
    for raw in specialists[:20]:
        if not isinstance(raw, dict):
            continue
        capability_id = str(raw.get("capability_id") or "").strip()
        if not capability_id or capability_id in seen:
            continue
        seen.add(capability_id)
        rows.append({
            "capability_id": capability_id,
            "app_name": str(raw.get("app_name") or raw.get("app_id") or "")[:120],
            "display_name": str(raw.get("display_name") or capability_id)[:160],
            "executable": raw.get("executable") is True,
            "reason_code": str(raw.get("reason_code") or "unknown")[:120],
            "runtime_available": raw.get("runtime_available") is True,
        })
    return rows


def _planning_schema(capability_ids: list[str]) -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "shine_concierge_capability_plan",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "selectedCapabilities": {
                        "type": "array",
                        "items": {"type": "string", "enum": capability_ids},
                        "maxItems": MAX_SPECIALISTS,
                    },
                    "clarificationNeeded": {"type": "boolean"},
                    "clarifyingQuestion": {"type": "string", "maxLength": 300},
                },
                "required": [
                    "selectedCapabilities",
                    "clarificationNeeded",
                    "clarifyingQuestion",
                ],
                "additionalProperties": False,
            },
        },
    }


def _safe_receipt(result: dict) -> dict:
    receipt = result.get("receipt") if isinstance(result.get("receipt"), dict) else {}
    return {
        "provider": str(result.get("provider") or "")[:80],
        "model_id": str(result.get("model_id") or "")[:120],
        "request_sha256": str(result.get("request_sha256") or "")[:128],
        "content_sha256": str(result.get("content_sha256") or "")[:128],
        "request_integrity": str(result.get("request_integrity") or "")[:80],
        "provider_transport_integrity": str(
            (receipt.get("provider_transport") or {}).get("integrity") or ""
        )[:80],
        "provider_response_integrity": str(
            (receipt.get("provider_response") or {}).get("integrity") or ""
        )[:80],
    }


def _status(steps: list[dict], clarification_needed: bool) -> str:
    if not steps:
        return "needs_input" if clarification_needed else "not_required"
    states = [step["status"] for step in steps]
    ready = sum(state == "ready" for state in states)
    if ready == len(states):
        return "ready"
    if ready:
        return "partial"
    if any(state == "needs_input" for state in states):
        return "needs_input"
    return "blocked"


def plan_concierge_specialists(
    message: str,
    fleet: dict | None,
    *,
    model_adapter,
    l_context: str = "",
) -> dict:
    """Return a validated, non-executing specialist plan.

    The only model-controlled field with operational meaning is the selected
    capability ID list, and every ID is revalidated against the live fleet.
    """
    clean_message = str(message or "").strip()
    if not clean_message:
        return {
            "status": "not_required",
            "reason_code": "empty-request",
            "steps": [],
            "selected_capabilities": [],
        }
    if len(clean_message) > MAX_MESSAGE_CHARS:
        return {
            "status": "needs_input",
            "reason_code": "concierge-request-too-large",
            "steps": [],
            "selected_capabilities": [],
        }

    catalogue = _catalogue(fleet)
    capability_ids = [row["capability_id"] for row in catalogue]
    if not capability_ids:
        return {
            "status": "blocked",
            "reason_code": "concierge-live-fleet-unavailable",
            "steps": [],
            "selected_capabilities": [],
        }
    if model_adapter is None or not getattr(model_adapter, "available", False):
        return {
            "status": "unavailable",
            "reason_code": "shine-ai-planner-unavailable",
            "steps": [],
            "selected_capabilities": [],
        }

    bounded_context = str(l_context or "")[:MAX_CONTEXT_CHARS]
    system = (
        "You are Shine AI acting only as a capability selector for Concierge. "
        "Choose zero to four capability IDs from the supplied live Foundation catalogue. "
        "Select every specialist materially needed for the user's request, including multiple "
        "specialists when the request genuinely spans domains. Never invent a capability. "
        "Do not call tools, do not answer the user, do not create specialist arguments, and do "
        "not infer missing required facts from memory. L context may help determine relevance "
        "only; required specialist inputs will be compiled separately from explicit user text. "
        "If the request clearly needs a specialist but the user's wording is too ambiguous to "
        "choose safely, set clarificationNeeded true and provide one short clarifying question. "
        "If no listed specialist is relevant, return an empty selection."
    )
    planning_context = {
        "userRequest": clean_message,
        "liveFoundationCatalogue": catalogue,
        "boundedLContext": bounded_context,
        "authority": {
            "modelMaySelectCapabilities": True,
            "modelMayConstructInputs": False,
            "modelMayExecute": False,
            "foundationRemainsFinalAuthority": True,
        },
    }
    request = build_model_request(
        [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": json.dumps(
                    planning_context,
                    ensure_ascii=False,
                    separators=(",", ":"),
                ),
            },
        ],
        purpose="shine_concierge_capability_planning",
        routing_purpose="shine_concierge_planning",
        response_format=_planning_schema(capability_ids),
        temperature=0.0,
        max_output_tokens=600,
    )

    try:
        result = invoke_model(model_adapter, request)
        raw = json.loads(result["content"])
    except Exception:
        return {
            "status": "unavailable",
            "reason_code": "shine-ai-plan-invalid",
            "steps": [],
            "selected_capabilities": [],
        }

    if not isinstance(raw, dict):
        return {
            "status": "unavailable",
            "reason_code": "shine-ai-plan-invalid",
            "steps": [],
            "selected_capabilities": [],
        }

    selected = raw.get("selectedCapabilities")
    clarification_needed = raw.get("clarificationNeeded")
    clarifying_question = raw.get("clarifyingQuestion")
    if (
        not isinstance(selected, list)
        or not isinstance(clarification_needed, bool)
        or not isinstance(clarifying_question, str)
        or len(selected) > MAX_SPECIALISTS
        or len(clarifying_question) > 300
    ):
        return {
            "status": "unavailable",
            "reason_code": "shine-ai-plan-invalid",
            "steps": [],
            "selected_capabilities": [],
        }

    normalised = [str(item) for item in selected]
    if len(set(normalised)) != len(normalised) or any(
        capability_id not in capability_ids for capability_id in normalised
    ):
        return {
            "status": "unavailable",
            "reason_code": "shine-ai-plan-invalid",
            "steps": [],
            "selected_capabilities": [],
        }

    by_id = {row["capability_id"]: row for row in catalogue}
    steps = []
    for capability_id in normalised:
        fleet_row = by_id[capability_id]
        contract = compile_specialist_input(capability_id, clean_message)
        if not fleet_row["executable"]:
            step_status = "blocked"
            reason_code = fleet_row["reason_code"]
        elif contract.get("status") != "ready":
            step_status = "needs_input"
            reason_code = str(contract.get("reason_code") or "specialist-input-missing")
        else:
            step_status = "ready"
            reason_code = "specialist-ready"
        step = {
            "capability_id": capability_id,
            "app_name": fleet_row["app_name"],
            "display_name": fleet_row["display_name"],
            "status": step_status,
            "reason_code": reason_code,
            "runtime_available": fleet_row["runtime_available"],
            "executable": fleet_row["executable"],
            "input_contract": contract,
        }
        steps.append(step)

    plan_status = _status(steps, clarification_needed)
    plan = {
        "status": plan_status,
        "reason_code": {
            "ready": "shine-ai-plan-ready",
            "partial": "shine-ai-plan-partial",
            "needs_input": "shine-ai-plan-needs-input",
            "blocked": "shine-ai-plan-blocked",
            "not_required": "shine-ai-plan-not-required",
        }[plan_status],
        "selected_capabilities": normalised,
        "steps": steps,
        "clarification_needed": clarification_needed,
        "clarifying_question": clarifying_question.strip(),
        "model_receipt": _safe_receipt(result),
        "catalogue_fingerprint": sha256(
            json.dumps(catalogue, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:16],
        "governance": {
            "selection_only": True,
            "inputs_compiled_deterministically": True,
            "execution_performed": False,
            "foundation_final_authority": True,
        },
    }
    if clarification_needed and plan_status == "ready":
        plan["status"] = "needs_input"
        plan["reason_code"] = "shine-ai-plan-needs-input"
    return plan
