"""Bind governed Concierge routes to Foundation execution and L synthesis evidence."""

from __future__ import annotations

import json

from services.foundation_companion_service import (
    invoke_foundation_orchestration,
    set_pending_concierge_job_status,
)


MAX_SYNTHESIS_EVIDENCE_CHARS = 12000
FOUNDATION_SYNC_TIMEOUT_SECONDS = 145.0


def _plan_from_route(route: dict) -> dict | None:
    if not isinstance(route, dict):
        return None
    capability = str(route.get("capability") or "")
    if capability == "foundation_orchestration":
        plan = route.get("foundation_orchestration")
        return plan if isinstance(plan, dict) else None

    if capability != "foundation_specialist":
        return None

    specialist = route.get("foundation_specialist")
    if not isinstance(specialist, dict):
        return None
    capability_id = str(specialist.get("capability_id") or "")
    if not capability_id:
        return None
    step_status = str(route.get("status") or "blocked")
    return {
        "status": step_status,
        "reason_code": str(
            specialist.get("reason_code") or "specialist-route-unavailable"
        ),
        "selected_capabilities": [capability_id],
        "steps": [{
            "capability_id": capability_id,
            "app_name": str(specialist.get("app_name") or ""),
            "display_name": str(
                specialist.get("display_name") or capability_id
            ),
            "status": step_status,
            "reason_code": str(
                specialist.get("reason_code") or "specialist-route-unavailable"
            ),
            "runtime_available": specialist.get("runtime_available") is True,
            "executable": specialist.get("executable") is True,
            "input_contract": specialist.get("input_contract"),
        }],
        "clarification_needed": step_status == "needs_input",
        "clarifying_question": "",
        "governance": {
            "selection_only": False,
            "inputs_compiled_deterministically": True,
            "execution_performed": False,
            "foundation_final_authority": True,
        },
    }


def execute_concierge_route(
    db,
    user_id: str,
    *,
    request_id: str,
    route: dict,
    foundation_url: str | None = None,
    post_impl=None,
    source_conversation_id: str | None = None,
    source_message_id: str | None = None,
) -> dict:
    """Execute a single- or multi-specialist route only through Foundation."""
    plan = _plan_from_route(route)
    if plan is None:
        return {
            "status": "not_required",
            "reason_code": "concierge-execution-not-required",
            "execution_performed": False,
            "synthesis_ready": False,
            "results": [],
        }
    execution = invoke_foundation_orchestration(
        db,
        user_id,
        request_id=request_id,
        orchestration_plan=plan,
        foundation_url=foundation_url,
        timeout_seconds=FOUNDATION_SYNC_TIMEOUT_SECONDS,
        post_impl=post_impl,
        source_conversation_id=source_conversation_id,
        source_message_id=source_message_id,
    )

    local_state = "unchanged"
    try:
        status = str(execution.get("status") or "")
        if status == "completed":
            set_pending_concierge_job_status(
                db, user_id=user_id, job_id=request_id, status="completed"
            )
            local_state = "completed"
        elif status == "partial":
            next_state = "ready" if execution.get("retry_scheduled") is True else "failed"
            set_pending_concierge_job_status(
                db, user_id=user_id, job_id=request_id, status=next_state
            )
            local_state = next_state
        elif status in {"blocked", "denied", "failed", "invalid"}:
            set_pending_concierge_job_status(
                db, user_id=user_id, job_id=request_id, status="failed"
            )
            local_state = "failed"
        elif status == "unavailable" and execution.get("execution_performed") is False:
            local_state = "not-created-or-unchanged"
        elif status == "unavailable":
            # Network uncertainty after execute may mean Foundation committed work
            # and queued a retry. Preserve the exact local inputs until the
            # Foundation retry queue proves the terminal outcome.
            local_state = "ready-uncertain"
    except Exception:
        local_state = "update-failed"

    return {**execution, "local_retry_state": local_state}


def _execution_summary(execution: dict) -> dict:
    return {
        "status": str(execution.get("status") or "unavailable"),
        "reason_code": str(execution.get("reason_code") or ""),
        "foundation_status": str(execution.get("foundation_status") or ""),
        "foundation_reason_code": str(
            execution.get("foundation_reason_code") or ""
        ),
        "selected_capabilities": list(
            execution.get("selected_capabilities") or []
        )[:4],
        "executed_capabilities": list(
            execution.get("executed_capabilities") or []
        )[:4],
        "completed_capabilities": list(
            execution.get("completed_capabilities") or []
        )[:4],
        "unavailable_capabilities": list(
            execution.get("unavailable_capabilities") or []
        )[:4],
        "skipped_capabilities": list(
            execution.get("skipped_capabilities") or []
        )[:4],
        "execution_performed": execution.get("execution_performed") is True,
        "retry_scheduled": execution.get("retry_scheduled") is True,
        "synthesis_ready": execution.get("synthesis_ready") is True,
        "synthesis_must_disclose_partial": (
            execution.get("synthesis_must_disclose_partial") is True
        ),
    }


def bind_concierge_execution(route: dict, execution: dict) -> dict:
    """Attach execution truth to the route and expose bounded evidence to L."""
    bound = dict(route or {})
    if not isinstance(execution, dict):
        return bound
    bound["foundation_execution"] = _execution_summary(execution)
    status = str(execution.get("status") or bound.get("status") or "unavailable")
    bound["status"] = status

    if execution.get("synthesis_ready") is not True:
        bound["handled"] = False
        bound["reply"] = ""
        return bound

    evidence = {
        "status": status,
        "reason_code": str(execution.get("reason_code") or ""),
        "foundation_status": str(execution.get("foundation_status") or ""),
        "completed_capabilities": list(
            execution.get("completed_capabilities") or []
        )[:4],
        "unavailable_capabilities": list(
            execution.get("unavailable_capabilities") or []
        )[:4],
        "skipped_capabilities": list(
            execution.get("skipped_capabilities") or []
        )[:4],
        "results": list(execution.get("results") or [])[:4],
        "retry_scheduled": execution.get("retry_scheduled") is True,
        "synthesis_must_disclose_partial": (
            execution.get("synthesis_must_disclose_partial") is True
        ),
    }
    encoded = json.dumps(
        evidence,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    if len(encoded) > MAX_SYNTHESIS_EVIDENCE_CHARS:
        compact_results = []
        for row in evidence["results"]:
            if not isinstance(row, dict):
                continue
            result = row.get("result")
            preview = ""
            if isinstance(result, dict):
                preview = json.dumps(
                    result,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    default=str,
                )[:2200]
            compact_results.append({
                "capability_id": row.get("capability_id"),
                "app_name": row.get("app_name"),
                "display_name": row.get("display_name"),
                "status": row.get("status"),
                "reason_code": row.get("reason_code"),
                "result_preview": preview,
                "result_truncated": bool(preview),
            })
        evidence["results"] = compact_results
        evidence["result_payloads_truncated_for_context_budget"] = True
        encoded = json.dumps(
            evidence,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )

    if len(encoded) > MAX_SYNTHESIS_EVIDENCE_CHARS:
        bound["handled"] = False
        bound["reply"] = ""
        bound["status"] = "unavailable"
        bound["foundation_execution"] = {
            **_execution_summary(execution),
            "status": "unavailable",
            "reason_code": "concierge-synthesis-evidence-too-large",
            "synthesis_ready": False,
        }
        return bound

    bound["handled"] = True
    bound["reply"] = encoded
    return bound
