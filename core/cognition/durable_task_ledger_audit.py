"""Layer 111: durable task ledger consistency audit.

Project L's durable queue is a state machine as well as a saved-answer store.
This audit verifies owner-scoped task-journal invariants, request hashes and
lease state without replaying work or mutating the queue.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256

from core.cognition.durable_tasks import owner_identity, request_hash


VERSION = "layer111-durable-task-ledger-audit-1"
PAGE_SIZE = 100
MAX_ROWS = 10000
ALLOWED_STATUSES = {"queued", "running", "ready", "failed", "interrupted"}
TERMINAL_STATUSES = {"ready", "failed"}


def _request_ref(request_id: object) -> str:
    return sha256(str(request_id or "").encode("utf-8")).hexdigest()[:12]


def _parse_time(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def audit_task_row(row: dict, *, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    issues: list[str] = []
    request_id = row.get("request_id")
    status = str(row.get("status") or "")
    checkpoint = row.get("checkpoint")
    worker_id = row.get("worker_id")
    lease_until = _parse_time(row.get("lease_until"))
    created_at = _parse_time(row.get("created_at"))
    updated_at = _parse_time(row.get("updated_at"))
    result = row.get("result")
    request = row.get("request")
    input_hash = str(row.get("input_hash") or "")
    owner_hash = str(row.get("owner_hash") or "")

    if status not in ALLOWED_STATUSES:
        issues.append("invalid_task_status")
    if not isinstance(checkpoint, str) or not checkpoint:
        issues.append("checkpoint_missing")
    if len(owner_hash) != 64:
        issues.append("owner_hash_shape_invalid")
    if len(input_hash) != 64:
        issues.append("input_hash_shape_invalid")

    if not isinstance(request, dict):
        issues.append("request_payload_missing_or_malformed")
    else:
        try:
            expected_hash = request_hash(request)
        except Exception:
            expected_hash = ""
            issues.append("request_payload_not_hashable")
        if expected_hash and input_hash != expected_hash:
            issues.append("request_hash_mismatch")
        embedded = str(request.get("request_id") or "")
        if embedded and str(request_id or "") != embedded:
            issues.append("request_id_binding_mismatch")

    if created_at is None:
        issues.append("created_at_invalid")
    if updated_at is None:
        issues.append("updated_at_invalid")
    if created_at and updated_at and updated_at < created_at:
        issues.append("updated_before_created")

    if status == "queued":
        if worker_id:
            issues.append("queued_task_has_worker")
        if lease_until is not None:
            issues.append("queued_task_has_lease")
        if result is not None:
            issues.append("queued_task_has_result")

    if status == "running":
        if not worker_id:
            issues.append("running_task_missing_worker")
        if lease_until is None:
            issues.append("running_task_missing_or_invalid_lease")
        elif lease_until < now:
            issues.append("running_task_lease_expired")
        if result is not None:
            issues.append("running_task_has_result")

    if status in TERMINAL_STATUSES:
        if checkpoint != status:
            issues.append("terminal_checkpoint_mismatch")
        if not isinstance(result, dict):
            issues.append("terminal_result_missing_or_malformed")

    if status == "interrupted":
        if result is not None:
            issues.append("interrupted_task_has_result")
        if lease_until is not None and lease_until >= now:
            issues.append("interrupted_task_has_live_lease")

    return {
        "request_ref": _request_ref(request_id),
        "status": status or "missing",
        "valid": not issues,
        "issues": issues,
    }


def summarise_task_ledger(
    rows,
    *,
    scan_complete: bool,
    capped: bool,
    now: datetime | None = None,
) -> dict:
    now = now or datetime.now(timezone.utc)
    statuses = Counter()
    issue_codes = Counter()
    observed = 0
    valid = 0
    malformed = 0
    findings = []

    for row in rows:
        if not isinstance(row, dict):
            malformed += 1
            issue_codes["malformed_task_row"] += 1
            continue
        observed += 1
        audit = audit_task_row(row, now=now)
        statuses[audit["status"]] += 1
        if audit["valid"]:
            valid += 1
        else:
            for issue in audit["issues"]:
                issue_codes[issue] += 1
            findings.append({
                "request_ref": audit["request_ref"],
                "status": audit["status"],
                "issues": audit["issues"][:16],
            })

    complete = bool(scan_complete and not capped)
    invalid = observed - valid
    if not complete:
        status = "incomplete_scan"
    elif invalid or malformed:
        status = "complete_with_ledger_issues"
    elif observed == 0:
        status = "complete_no_tasks"
    else:
        status = "complete_healthy"

    return {
        "version": VERSION,
        "mode": "durable_task_ledger_audit",
        "generated_at": now.isoformat(),
        "status": status,
        "scan_complete": complete,
        "capped": bool(capped),
        "tasks_observed": observed,
        "valid_task_rows": valid,
        "invalid_task_rows": invalid,
        "malformed_rows": malformed,
        "task_statuses": dict(statuses),
        "issue_codes": dict(issue_codes),
        "findings": findings[:50],
        "checks": {
            "request_hash_binding": True,
            "request_id_binding": True,
            "state_machine_shape": True,
            "terminal_result_contract": True,
            "running_lease_liveness": True,
            "timestamp_ordering": True,
        },
        "actions": {
            "tasks_replayed": False,
            "leases_changed": False,
            "rows_changed": False,
            "memory_written": False,
            "automatic_repair": False,
        },
        "privacy": {
            "request_payloads_returned": False,
            "answer_text_returned": False,
            "raw_request_ids_returned": False,
            "owner_hashes_returned": False,
            "input_hashes_returned": False,
            "secret_values_returned": False,
            "finding_refs": "sha256_prefix_12",
        },
        "claims": {
            "ledger_coverage": "complete" if complete else "incomplete",
            "ledger_consistency": (
                "verified"
                if complete and invalid == 0 and malformed == 0
                else "not_verified"
            ),
            "answer_quality": "not_scored",
            "factual_correctness": "not_scored",
        },
        "limitations": [
            "The audit verifies durable task-journal invariants, not business-level correctness of a request.",
            "A capped or interrupted scan cannot certify the full owner ledger.",
            "Detected issues are reported only; no task is replayed or repaired automatically.",
        ],
    }


def load_task_ledger_audit(
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
        page = (
            client.table("l_chat_tasks")
            .select(
                "request_id,owner_hash,input_hash,request,status,checkpoint,"
                "worker_id,lease_until,result,created_at,updated_at"
            )
            .eq("user_id", user_id)
            .eq("owner_hash", owner_hash)
            .order("created_at", desc=False)
            .range(offset, offset + batch_size - 1)
            .execute()
            .data
        )
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

    report = summarise_task_ledger(
        rows,
        scan_complete=scan_complete,
        capped=capped,
    )
    report["scan"] = {
        "scope": "recovery_token_owner_all_durable_tasks",
        "database": "l_chat_tasks",
        "order": "oldest_first",
        "page_size": page_size,
        "pages_read": pages_read,
        "max_rows": max_rows,
        "rows_read": len(rows),
        "read_only": True,
    }
    return report
