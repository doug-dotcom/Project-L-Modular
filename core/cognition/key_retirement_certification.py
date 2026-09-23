"""Layer 109: exhaustive signing-key dependency certification.

Recent-sample audits cannot prove that a historical signing key is unused.
This module scans an owner's durable saved-answer history page by page, counts
every stored key reference conservatively (including invalid records), and only
marks a zero-reference key eligible for operator review when the scan completes.
It never mutates keys or data.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from core.cognition.answer_authenticity import authenticity_status
from core.cognition.durable_tasks import owner_identity
from core.cognition.recovery_provenance import verify_recovered_answer_payload


VERSION = "layer109-key-retirement-certification-1"
PAGE_SIZE = 100
MAX_ROWS = 10000
LEGACY_KEY_LABEL = "legacy_layer104"


def _object(value):
    return value if isinstance(value, dict) else {}


def _raw_auth_dependency(result: object) -> str:
    if not isinstance(result, dict):
        return ""
    cognition = _object(result.get("cognition"))
    auth = _object(cognition.get("answer_authenticity"))
    if not auth:
        return ""

    version = str(auth.get("version") or "")
    key_id = str(auth.get("key_id") or "").strip().lower()
    if key_id:
        return key_id[:32]
    if version == "layer104-answer-authenticity-1":
        return LEGACY_KEY_LABEL
    return "unclassified_signed_reference"


def summarise_key_dependencies(
    rows,
    *,
    scan_complete: bool,
    capped: bool,
    configured_status: dict | None = None,
) -> dict:
    status = dict(configured_status or authenticity_status())
    dependencies = Counter()
    verification_states = Counter()
    issue_codes = Counter()
    observed = 0
    malformed = 0
    ready_without_result = 0

    for row in rows:
        if not isinstance(row, dict):
            malformed += 1
            continue
        request_id = row.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            malformed += 1
            continue

        observed += 1
        result = row.get("result")
        dependency = _raw_auth_dependency(result)
        if dependency:
            dependencies[dependency] += 1

        if not isinstance(result, dict):
            if row.get("status") == "ready":
                ready_without_result += 1
                issue_codes["ready_without_result"] += 1
            verification_states["not_checked"] += 1
            continue

        check = verify_recovered_answer_payload(
            result,
            expected_request_id=request_id,
        )
        state = str(check.get("status") or "unknown")[:80]
        verification_states[state] += 1

        for source in (
            check.get("issues") or [],
            _object(check.get("answer_provenance")).get("issues") or [],
            _object(check.get("answer_authenticity")).get("issues") or [],
        ):
            for issue in source:
                if isinstance(issue, str):
                    issue_codes[issue[:120]] += 1

    active = str(status.get("active_key_id") or "")
    retained = [
        str(key_id)
        for key_id in (status.get("retained_key_ids") or [])
        if isinstance(key_id, str) and key_id
    ]

    candidates = []
    for key_id in retained:
        refs = int(dependencies.get(key_id, 0))
        if key_id == active:
            decision = "active_do_not_retire"
        elif refs:
            decision = "in_use"
        elif scan_complete and not capped:
            decision = "eligible_for_operator_review"
        else:
            decision = "unknown_incomplete_scan"
        candidates.append({
            "key_id": key_id,
            "stored_references": refs,
            "decision": decision,
            "automatic_retirement": False,
        })

    legacy_refs = int(dependencies.get(LEGACY_KEY_LABEL, 0))
    legacy_configured = status.get("legacy_verification_configured") is True
    if legacy_configured:
        if legacy_refs:
            legacy_decision = "in_use"
        elif scan_complete and not capped:
            legacy_decision = "eligible_for_operator_review"
        else:
            legacy_decision = "unknown_incomplete_scan"
        candidates.append({
            "key_id": LEGACY_KEY_LABEL,
            "stored_references": legacy_refs,
            "decision": legacy_decision,
            "automatic_retirement": False,
        })

    complete = bool(scan_complete and not capped)
    return {
        "version": VERSION,
        "mode": "signing_key_dependency_certification",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "complete" if complete else "incomplete",
        "scan_complete": complete,
        "capped": bool(capped),
        "answers_observed": observed,
        "malformed_rows_ignored": malformed,
        "ready_without_result": ready_without_result,
        "active_key_id": active,
        "retained_key_ids": retained,
        "stored_key_references": dict(dependencies),
        "verification_states": dict(verification_states),
        "issue_codes": dict(issue_codes),
        "retirement_candidates": candidates,
        "policy": {
            "automatic_retirement": False,
            "zero_reference_requirement": True,
            "complete_scan_required": True,
            "active_key_retirement_allowed": False,
            "operator_review_required": True,
        },
        "privacy": {
            "answer_text_returned": False,
            "prompt_text_returned": False,
            "evidence_text_returned": False,
            "raw_request_ids_returned": False,
            "secret_values_returned": False,
        },
        "claims": {
            "key_dependency_coverage": (
                "complete" if complete else "incomplete"
            ),
            "safe_to_auto_retire_any_key": False,
            "answer_quality": "not_scored",
            "factual_correctness": "not_scored",
        },
        "limitations": [
            "Eligibility means only that a complete scan found zero stored references.",
            "No key is retired automatically.",
            "A capped or interrupted scan cannot support zero-reference eligibility.",
            "Stored-reference counts do not establish answer quality or factual correctness.",
        ],
    }


def load_key_retirement_certification(
    client,
    recovery_token,
    *,
    page_size: int = PAGE_SIZE,
    max_rows: int = MAX_ROWS,
) -> dict:
    if type(page_size) is not int or not 1 <= page_size <= PAGE_SIZE:
        raise ValueError("page_size must be between 1 and 100")
    if type(max_rows) is not int or not 1 <= max_rows <= MAX_ROWS:
        raise ValueError("max_rows must be between 1 and 10000")

    user_id, owner_hash = owner_identity(recovery_token)
    if client is None:
        raise RuntimeError("database_unavailable")

    rows = []
    offset = 0
    scan_complete = False
    capped = False
    pages_read = 0

    while offset < max_rows:
        remaining = max_rows - offset
        batch_size = min(page_size, remaining)
        query = (
            client.table("l_chat_tasks")
            .select("request_id,created_at,status,result")
            .eq("user_id", user_id)
            .eq("owner_hash", owner_hash)
            .order("created_at", desc=False)
            .range(offset, offset + batch_size - 1)
        )
        page = query.execute().data
        if not isinstance(page, list):
            raise RuntimeError("invalid_database_response")

        pages_read += 1
        rows.extend(page)

        if len(page) < batch_size:
            scan_complete = True
            break

        offset += batch_size

    if not scan_complete and len(rows) >= max_rows:
        capped = True

    report = summarise_key_dependencies(
        rows,
        scan_complete=scan_complete,
        capped=capped,
    )
    report["scan"] = {
        "scope": "recovery_token_owner_all_saved_tasks",
        "database": "l_chat_tasks",
        "order": "oldest_first",
        "page_size": page_size,
        "pages_read": pages_read,
        "max_rows": max_rows,
        "rows_read": len(rows),
        "read_only": True,
    }
    return report
