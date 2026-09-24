"""Layer 108: owner-scoped cold recovery certification for one saved answer.

A cold recovery certification reads only the durable task record, never the
in-process cache, and verifies the stored result with the current delivery,
provenance, authenticity and keyring contracts. It does not replay the task,
call a model, or mutate storage.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID

from core.cognition.durable_tasks import owner_identity
from core.cognition.recovery_provenance import (
    PROTOCOL_KEY,
    SUPPORTED_PROTOCOLS,
    verify_recovered_answer_payload,
)
from core.cognition.release_provenance import build_release_provenance


VERSION = "layer114-cold-recovery-certification-2"
TASK_STATUSES = {"queued", "running", "ready", "failed", "interrupted"}
TERMINAL_STATUSES = {"ready", "failed"}


def _object(value):
    return value if isinstance(value, dict) else {}


def _normalise_request_id(value) -> str:
    try:
        return str(UUID(str(value or "")))
    except (TypeError, ValueError, AttributeError):
        return ""


def _safe_request_ref(request_id: str) -> str:
    return sha256(str(request_id).encode("utf-8")).hexdigest()[:12]


def _issues_from(check: dict) -> list[str]:
    combined = []
    for source in (
        check.get("issues") or [],
        _object(check.get("answer_provenance")).get("issues") or [],
        _object(check.get("answer_authenticity")).get("issues") or [],
    ):
        for issue in source:
            if isinstance(issue, str) and issue not in combined:
                combined.append(issue[:120])
    return combined[:20]


def certify_saved_answer_row(
    row: dict | None,
    *,
    request_id: str,
    current_release: dict | None = None,
) -> dict:
    request_id = _normalise_request_id(request_id)
    if not request_id:
        raise ValueError("A valid request ID is required")

    request_ref = _safe_request_ref(request_id)
    release = (
        build_release_provenance()
        if current_release is None
        else dict(current_release or {})
    )
    current_commit = str(release.get("commit_sha") or "")[:40]
    current_release_verified = bool(
        release.get("verified") is True
        and release.get("status") == "verified_production"
    )

    base = {
        "version": VERSION,
        "mode": "cold_saved_answer_recovery_certification",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "request_ref": request_ref,
        "read_only": True,
        "task_replayed": False,
        "model_called": False,
        "memory_written": False,
        "current_release": {
            "verified_production": current_release_verified,
            "commit_sha": current_commit,
        },
        "privacy": {
            "answer_text_returned": False,
            "prompt_text_returned": False,
            "evidence_text_returned": False,
            "raw_request_id_returned": False,
            "secret_values_returned": False,
        },
        "claims": {
            "recoverability": "not_certified",
            "answer_quality": "not_scored",
            "factual_correctness": "not_scored",
            "memory_quality": "not_scored",
        },
    }

    if not isinstance(row, dict):
        return {
            **base,
            "status": "not_found",
            "certified": False,
            "stored_task_status": "not_found",
            "release_relationship": "unknown",
            "issues": ["saved_task_not_found"],
        }

    raw_status = row.get("status")
    stored_status = (
        raw_status if isinstance(raw_status, str) and raw_status in TASK_STATUSES
        else "invalid"
    )
    result = row.get("result")
    preflight_status = ""
    issue = ""
    if stored_status == "invalid":
        preflight_status, issue = "failed_task_state", "saved_task_status_invalid"
    elif stored_status not in TERMINAL_STATUSES:
        if result is None:
            preflight_status, issue = "not_ready", "saved_answer_not_ready"
        else:
            preflight_status, issue = "failed_task_state", "nonterminal_task_has_result"
    elif not isinstance(result, dict):
        preflight_status = "failed_integrity"
        issue = "ready_without_result" if stored_status == "ready" else "terminal_result_missing_or_malformed"

    if preflight_status:
        return {
            **base,
            "status": preflight_status,
            "certified": False,
            "stored_task_status": stored_status,
            "release_relationship": "unknown",
            "protocol_version": "",
            "delivery": {"valid": False, "bound": False},
            "provenance": {"present": False, "valid": False},
            "authenticity": {
                "required": False,
                "present": False,
                "valid": False,
                "verification_mode": "",
                "key_id": "",
            },
            "issues": [issue],
            "claims": {
                **base["claims"],
                "recoverability": "not_certified" if preflight_status == "not_ready" else "failed",
            },
        }

    check = verify_recovered_answer_payload(
        result,
        expected_request_id=request_id,
    )
    delivery = _object(check.get("delivery_integrity"))
    provenance_check = _object(check.get("answer_provenance"))
    authenticity_check = _object(check.get("answer_authenticity"))
    cognition = _object(result.get("cognition"))
    provenance = _object(cognition.get("answer_provenance"))
    protocol = result.get(PROTOCOL_KEY)
    if PROTOCOL_KEY not in result:
        protocol = ""
    elif not isinstance(protocol, str) or protocol not in SUPPORTED_PROTOCOLS:
        protocol = "unsupported"
    stored_commit = str(provenance.get("release_commit_sha") or "")[:40]
    provenance_present = bool(provenance)
    authenticity_present = isinstance(cognition.get("answer_authenticity"), dict)

    if stored_commit and current_commit:
        release_relationship = (
            "current_release"
            if stored_commit == current_commit
            else "historical_release"
        )
    elif stored_commit:
        release_relationship = "stored_release_only"
    else:
        release_relationship = "legacy_no_release_provenance"

    valid = check.get("valid") is True
    modern_authenticated = bool(
        valid
        and check.get("authenticity_required") is True
        and authenticity_check.get("valid") is True
        and authenticity_check.get("authentic") is True
    )

    if not valid:
        status = "failed_integrity"
        certified = False
        recoverability = "failed"
    elif modern_authenticated and release_relationship == "current_release":
        status = "certified_current_release"
        certified = True
        recoverability = "certified"
    elif modern_authenticated:
        status = "certified_historical_release"
        certified = True
        recoverability = "certified"
    elif provenance_present and provenance_check.get("valid") is True:
        status = "certified_provenance_compatibility"
        certified = True
        recoverability = "certified_compatibility"
    else:
        status = "legacy_readable_not_modernly_authenticated"
        certified = True
        recoverability = "certified_legacy_readability"

    issues = _issues_from(check)
    return {
        **base,
        "status": status,
        "certified": certified,
        "stored_task_status": stored_status,
        "recovery_status": str(check.get("status") or "")[:80],
        "release_relationship": release_relationship,
        "protocol_version": protocol[:40],
        "stored_release_commit_sha": stored_commit,
        "delivery": {
            "valid": delivery.get("valid") is True,
            "bound": delivery.get("bound") is True,
        },
        "provenance": {
            "present": provenance_present,
            "valid": provenance_check.get("valid") is True,
            "verified_production": provenance_check.get("verified_production") is True,
        },
        "authenticity": {
            "required": check.get("authenticity_required") is True,
            "present": authenticity_present,
            "valid": authenticity_check.get("valid") is True,
            "authentic": authenticity_check.get("authentic") is True,
            "verification_mode": str(
                authenticity_check.get("verification_mode") or ""
            )[:40],
            "key_id": str(authenticity_check.get("key_id") or "")[:32],
        },
        "issues": issues,
        "claims": {
            **base["claims"],
            "recoverability": recoverability,
        },
        "limitations": [
            "Certification verifies persistent stored-answer recovery contracts only.",
            "Historical release verification is not a claim that the old release was better or worse.",
            "Legacy readability may be valid without modern provenance or HMAC authentication.",
            "Recoverability does not establish factual correctness or answer quality.",
        ],
    }


def load_cold_recovery_certification(
    client,
    recovery_token,
    request_id,
) -> dict:
    request_id = _normalise_request_id(request_id)
    if not request_id:
        raise ValueError("A valid request ID is required")
    user_id, owner_hash = owner_identity(recovery_token)
    if client is None:
        raise RuntimeError("database_unavailable")

    rows = (
        client.table("l_chat_tasks")
        .select("request_id,created_at,updated_at,status,result")
        .eq("request_id", request_id)
        .eq("user_id", user_id)
        .eq("owner_hash", owner_hash)
        .limit(1)
        .execute()
        .data
    )
    if not isinstance(rows, list):
        raise RuntimeError("invalid_database_response")

    report = certify_saved_answer_row(
        rows[0] if rows else None,
        request_id=request_id,
    )
    report["sample"] = {
        "scope": "recovery_token_owner_exact_request",
        "database": "l_chat_tasks",
        "read_only": True,
        "limit": 1,
        "in_process_cache_used": False,
    }
    return report
