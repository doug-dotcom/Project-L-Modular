"""Deterministic capability routing. Services do not become L personalities."""

from __future__ import annotations

from core.cognition.action_receipt import verify_action_receipt
from services.concierge_specialist_inputs import compile_specialist_input
from core.cognition.durable_tasks import (
    DurableTaskBindingError,
    current_task_request_id,
    record_current_action_receipt,
)


def _normalise(message: str) -> str:
    return str(message or "").strip().lower()


FOUNDATION_SPECIALIST_HINTS = {
    "fiona.company_brief": (
        "fiona", "company brief", "company evidence brief",
    ),
    "money.explain_calculate": (
        "my money", "money calculation", "compound interest", "explain money",
    ),
    "daash.exercise_explain": (
        "daash", "explain exercise", "exercise technique", "what muscles",
    ),
    "translate.text": (
        "shine translate", "translate:", "translate this", "translate to", "how do you say",
    ),
    "travel.plan_trip": (
        "shine travel", "travel sherpa", "plan a trip", "plan my trip", "holiday plan",
    ),
    "dive.destination_brief": (
        "shine dive", "dive brief", "scuba brief", "dive destination",
    ),
    "fish.destination_brief": (
        "shine fish", "fishing brief", "fish destination",
    ),
    "ski.destination_brief": (
        "shine ski", "ski brief", "snow brief", "ski destination",
    ),
    "dnd.campaign_context": (
        "shine d&d", "shine dnd", "d&d campaign", "dnd campaign",
    ),
}


def foundation_specialist_interest(message: str) -> bool:
    text = _normalise(message)
    return any(
        hint in text
        for hints in FOUNDATION_SPECIALIST_HINTS.values()
        for hint in hints
    )


def _foundation_matches(text: str) -> list[str]:
    return [
        capability
        for capability, hints in FOUNDATION_SPECIALIST_HINTS.items()
        if any(hint in text for hint in hints)
    ]


def _foundation_candidate(text: str) -> str | None:
    matches = _foundation_matches(text)
    return matches[0] if len(matches) == 1 else None


def needs_concierge_planning(message: str) -> bool:
    """Use Shine AI only when deterministic specialist routing is ambiguous."""
    text = _normalise(message)
    return len(_foundation_matches(text)) > 1


def _foundation_route_packet(fleet: dict | None, capability_id: str) -> dict:
    status = str((fleet or {}).get("status") or "unavailable")
    specialists = (fleet or {}).get("specialists")
    specialists = specialists if isinstance(specialists, list) else []
    selected = next(
        (
            item for item in specialists
            if isinstance(item, dict) and item.get("capability_id") == capability_id
        ),
        None,
    )
    if selected is None:
        return {
            "fleet_status": status,
            "capability_id": capability_id,
            "executable": False,
            "reason_code": str((fleet or {}).get("reason_code") or "specialist-not-in-live-fleet"),
        }
    return {
        "fleet_status": status,
        "specialist_count": int((fleet or {}).get("specialist_count") or len(specialists)),
        "executable_count": int((fleet or {}).get("executable_count") or 0),
        "blocked_count": int((fleet or {}).get("blocked_count") or 0),
        "app_id": str(selected.get("app_id") or ""),
        "app_name": str(selected.get("app_name") or ""),
        "capability_id": capability_id,
        "display_name": str(selected.get("display_name") or capability_id),
        "executable": selected.get("executable") is True,
        "reason_code": str(selected.get("reason_code") or "unknown"),
        "runtime_available": selected.get("runtime_available") is True,
    }


def _personal_reflection(text: str) -> bool:
    return any(signal in text for signal in (
        "my journey", "how do i feel", "what do you think about me", "my trauma",
        "my recovery", "my spirituality", "my emotions", "my relationship",
    ))


def _run(capability: str, handler, message: str) -> dict:
    try:
        reply = handler(message)
        return {"handled": True, "capability": capability, "reply": reply, "status": "ok"}
    except DurableTaskBindingError:
        raise
    except Exception as exc:
        return {
            "handled": True,
            "capability": capability,
            "reply": f"{capability.replace('_', ' ').title()} service error: {exc}",
            "status": "error",
        }


def route_capability(
    message: str,
    write_guard=None,
    foundation_fleet=None,
    concierge_plan=None,
) -> dict:
    text = _normalise(message)

    from services.google_workspace_service import (
        calendar_summary,
        classify_google_capability,
        gmail_summary,
        tasks_result,
    )
    google_capability = classify_google_capability(message)
    google_handlers = {
        "gmail": gmail_summary,
        "calendar": calendar_summary,
        "tasks": tasks_result,
    }
    if google_capability:
        handler = google_handlers[google_capability]
        if google_capability == "tasks":
            receipt_box = {}
            def capture_receipt(receipt):
                # Preserve Layer 165's explicit uncertain-provider outcome when
                # Google does not return enough evidence for a valid receipt.
                # Only a semantically valid provider confirmation is eligible
                # for durable journaling.
                receipt_box["value"] = receipt
                verification = verify_action_receipt(
                    receipt,
                    expected_request_id=current_task_request_id(),
                )
                if verification.get("valid"):
                    record_current_action_receipt(receipt)

            result = _run(
                google_capability,
                lambda value: tasks_result(
                    value,
                    write_guard=write_guard,
                    receipt_sink=capture_receipt,
                ),
                message,
            )
            receipt = receipt_box.get("value")
            if receipt is not None:
                verification = verify_action_receipt(
                    receipt,
                    expected_request_id=current_task_request_id(),
                )
                result["action_receipt"] = receipt
                result["action_receipt_verification"] = verification
                if not verification.get("valid"):
                    result.update({
                        "status": "error",
                        "reply": (
                            "Google Tasks may have created the task, but L could not verify "
                            "the provider action receipt. Check Google Tasks before retrying."
                        ),
                    })
            return result
        return _run(google_capability, handler, message)

    finance_data_action = any(signal in text for signal in (
        "uploaded transactions", "transactions csv", "bank statement csv",
        "review my transactions", "analyse my transactions", "analyze my transactions",
    ))
    if finance_data_action:
        from agents.fiona import fiona
        if fiona.should_handle(text):
            return _run("financial_intelligence", fiona.handle_finance_request, message)

    foundation_candidate = _foundation_candidate(text)
    if foundation_candidate:
        specialist = _foundation_route_packet(foundation_fleet, foundation_candidate)
        input_contract = compile_specialist_input(foundation_candidate, message)
        specialist["input_contract"] = input_contract
        route_status = (
            "blocked"
            if not specialist["executable"]
            else "ready"
            if input_contract.get("status") == "ready"
            else "needs_input"
        )
        return {
            "handled": False,
            "capability": "foundation_specialist",
            "reply": "",
            "status": route_status,
            "foundation_specialist": specialist,
        }

    if isinstance(concierge_plan, dict):
        plan_status = str(concierge_plan.get("status") or "unavailable")
        selected = concierge_plan.get("selected_capabilities")
        selected = selected if isinstance(selected, list) else []
        if selected or plan_status not in {"not_required", ""}:
            return {
                "handled": False,
                "capability": "foundation_orchestration",
                "reply": "",
                "status": plan_status,
                "foundation_orchestration": concierge_plan,
            }

    if len(_foundation_matches(text)) > 1:
        return {
            "handled": False,
            "capability": "foundation_orchestration",
            "reply": "",
            "status": "unavailable",
            "foundation_orchestration": {
                "status": "unavailable",
                "reason_code": "concierge-planning-unavailable",
                "selected_capabilities": [],
                "steps": [],
            },
        }

    from services.external_research_service import research, should_handle
    if should_handle(message) and not _personal_reflection(text):
        try:
            return {
                "handled": True,
                "capability": "external_research",
                "reply": research(message),
                "status": "ok",
            }
        except Exception as exc:
            return {
                "handled": True,
                "capability": "external_research",
                "reply": f"External research service error: {exc}",
                "status": "error",
            }

    return {"handled": False, "capability": "l_core", "reply": "", "status": "not_required"}
