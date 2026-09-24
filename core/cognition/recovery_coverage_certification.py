"""Layer 110: exhaustive durable recovery coverage certification.

Layer 108 certifies one exact saved answer. Layer 110 scans an owner's durable
saved-answer history page by page and certifies aggregate recoverability under
the current verification code and keyring, without replaying any task.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID

from core.cognition.cold_recovery_certification import certify_saved_answer_row
from core.cognition.durable_tasks import owner_identity
from core.cognition.release_provenance import build_release_provenance


VERSION = "layer113-recovery-coverage-certification-2"
PAGE_SIZE = 100
MAX_ROWS = 10000


def summarise_recovery_coverage(
    rows,
    *,
    scan_complete: bool,
    capped: bool,
    current_release: dict | None = None,
) -> dict:
    release = (
        build_release_provenance()
        if current_release is None
        else dict(current_release or {})
    )
    statuses = Counter()
    release_relationships = Counter()
    issue_codes = Counter()
    failures = []
    findings_total = 0
    rows_observed = 0
    observed = 0
    malformed = 0
    verification_errors = 0
    failed = 0
    failed_ready = 0
    certified = 0
    modern_authenticated = 0
    legacy_readable = 0
    not_ready = 0

    def add_finding(request_id, status, issues):
        nonlocal findings_total
        findings_total += 1
        if len(failures) < 50:
            failures.append({
                "request_ref": sha256(request_id.encode("utf-8")).hexdigest()[:12] if request_id else "",
                "status": status,
                "issues": issues[:12],
            })

    for row in rows:
        rows_observed += 1
        request_id = row.get("request_id") if isinstance(row, dict) else None
        try:
            if not isinstance(request_id, str):
                raise ValueError("request_id_invalid")
            UUID(request_id)
        except ValueError:
            malformed += 1
            issue_codes["malformed_saved_task"] += 1
            add_finding(request_id if isinstance(request_id, str) else "",
                        "unassessed_record", ["malformed_saved_task"])
            continue

        observed += 1
        try:
            certificate = certify_saved_answer_row(
                row,
                request_id=request_id,
                current_release=release,
            )
            if not isinstance(certificate, dict):
                raise TypeError("certificate_not_an_object")
        except Exception:
            # A verifier failure is uncertainty, never evidence of recovery.
            # Continue the read-only scan without exposing exception content.
            verification_errors += 1
            issue_codes["recovery_verification_error"] += 1
            add_finding(request_id, "unassessed_record", ["recovery_verification_error"])
            continue

        status = str(certificate.get("status") or "unknown")[:80]
        relationship = str(
            certificate.get("release_relationship") or "unknown"
        )[:80]
        statuses[status] += 1
        release_relationships[relationship] += 1

        if certificate.get("certified") is True:
            certified += 1
        if status in {
            "certified_current_release",
            "certified_historical_release",
        } and certificate.get("authenticity", {}).get("authentic") is True:
            modern_authenticated += 1
        if status == "legacy_readable_not_modernly_authenticated":
            legacy_readable += 1
        if status in {"not_ready", "not_found"}:
            not_ready += 1
        elif certificate.get("certified") is not True:
            failed += 1
            if row.get("status") == "ready":
                failed_ready += 1

        issues = [
            issue
            for issue in (certificate.get("issues") or [])
            if isinstance(issue, str)
        ]
        for issue in issues:
            issue_codes[issue[:120]] += 1

        if certificate.get("certified") is not True:
            add_finding(request_id, status, issues)

    complete = bool(scan_complete and not capped)
    unassessed = malformed + verification_errors
    assessment_complete = bool(complete and unassessed == 0)
    all_ready_recoverable = bool(assessment_complete and failed == 0)
    all_observed_certified = bool(assessment_complete and certified == observed)

    if not complete:
        overall = "incomplete_scan"
    elif unassessed:
        overall = "complete_with_unassessed_records"
    elif observed == 0:
        overall = "complete_no_saved_answers"
    elif failed:
        overall = "complete_with_recovery_failures"
    elif not_ready:
        overall = "complete_with_incomplete_tasks"
    elif legacy_readable:
        overall = "complete_recoverable_with_legacy"
    else:
        overall = "complete_recoverable"

    return {
        "version": VERSION,
        "mode": "durable_recovery_coverage_certification",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": overall,
        "scan_complete": complete,
        "capped": bool(capped),
        "rows_observed": rows_observed,
        "answers_observed": observed,
        "malformed_rows": malformed,
        # Compatibility alias only: these rows now block coverage claims.
        "malformed_rows_ignored": malformed,
        "verification_error_rows": verification_errors,
        "unassessed_rows": unassessed,
        "certified_answers": certified,
        "modern_authenticated_answers": modern_authenticated,
        "legacy_readable_answers": legacy_readable,
        "not_ready_answers": not_ready,
        "failed_ready_answers": failed_ready,
        "failed_recovery_records": failed,
        "recovery_statuses": dict(statuses),
        "release_relationships": dict(release_relationships),
        "issue_codes": dict(issue_codes),
        "failure_findings": failures,
        "failure_findings_omitted": max(0, findings_total - len(failures)),
        "current_release": {
            "verified_production": bool(
                release.get("verified") is True
                and release.get("status") == "verified_production"
            ),
            "commit_sha": str(release.get("commit_sha") or "")[:40],
        },
        "coverage": {
            "all_ready_answers_recoverable": all_ready_recoverable,
            "all_observed_tasks_certified": all_observed_certified,
            "assessment_complete": assessment_complete,
            "unassessed_records_block_coverage": True,
            "complete_scan_required": True,
            "task_replay_used": False,
            "model_calls_used": False,
            "memory_writes_used": False,
        },
        "privacy": {
            "answer_text_returned": False,
            "prompt_text_returned": False,
            "evidence_text_returned": False,
            "raw_request_ids_returned": False,
            "request_refs": "sha256_prefix_12_for_failures_only",
            "secret_values_returned": False,
        },
        "claims": {
            "durable_recovery_coverage": (
                "complete"
                if assessment_complete
                else "unverified" if complete else "incomplete"
            ),
            "answer_quality": "not_scored",
            "factual_correctness": "not_scored",
            "memory_quality": "not_scored",
        },
        "limitations": [
            "Coverage applies only to durable l_chat_tasks records in the scanned owner history.",
            "A capped or interrupted scan cannot certify full-history recovery coverage.",
            "Malformed records or verifier errors block full-history recovery claims, even when the scan finishes.",
            "Legacy readability is not equivalent to modern HMAC authentication.",
            "Recoverability does not establish factual correctness or answer quality.",
        ],
    }


def load_recovery_coverage_certification(
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
            .select("request_id,created_at,updated_at,status,result")
            .eq("user_id", user_id)
            .eq("owner_hash", owner_hash)
            .order("created_at", desc=False)
            .order("request_id", desc=False)
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

    report = summarise_recovery_coverage(
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
        "in_process_cache_used": False,
    }
    return report
