"""Durable recovery coverage, hardened and shared with readiness in Layer 114.

Layer 108 certifies one exact saved answer. Layer 110 scans an owner's durable
saved-answer history page by page and certifies aggregate recoverability under
the current verification code and keyring, without replaying any task.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from core.cognition.cold_recovery_certification import certify_saved_answer_row
from core.cognition.durable_task_ledger_audit import scan_task_ledger
from core.cognition.release_provenance import build_release_provenance


VERSION = "layer114-recovery-coverage-certification-2"
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
    observed = 0
    malformed = 0
    certified = 0
    modern_authenticated = 0
    legacy_readable = 0
    not_ready = 0

    for row in rows:
        if not isinstance(row, dict):
            malformed += 1
            issue_codes["malformed_task_row"] += 1
            continue
        request_id = row.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            malformed += 1
            issue_codes["invalid_task_request_id"] += 1
            continue

        observed += 1
        try:
            certificate = certify_saved_answer_row(
                row,
                request_id=request_id,
                current_release=release,
            )
        except ValueError:
            malformed += 1
            issue_codes["invalid_task_request_id"] += 1
            observed -= 1
            continue

        status = str(certificate.get("status") or "unknown")[:80]
        # A terminal task with no saved result is a recovery failure, not a
        # pending task to subtract from the denominator of ready records.
        if status in {"not_ready", "not_found"} and row.get("status") not in (
            "queued", "running", "interrupted",
        ):
            status = "failed_missing_result"
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

        issues = [
            issue
            for issue in (certificate.get("issues") or [])
            if isinstance(issue, str)
        ]
        if status == "failed_missing_result":
            issues.append("saved_result_missing_or_malformed")
        for issue in issues:
            issue_codes[issue[:120]] += 1

        if certificate.get("certified") is not True and len(failures) < 50:
            failures.append({
                "request_ref": str(certificate.get("request_ref") or "")[:12],
                "status": status,
                "issues": issues[:12],
            })

    complete = bool(scan_complete and not capped)
    ready_records = max(0, observed - not_ready)
    failed = max(0, ready_records - certified)
    all_ready_recoverable = bool(complete and malformed == 0 and failed == 0)
    all_observed_certified = bool(complete and malformed == 0 and certified == observed)

    if not complete:
        overall = "incomplete_scan"
    elif malformed:
        overall = "complete_with_malformed_records"
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
        "answers_observed": observed,
        "malformed_rows_ignored": malformed,
        "certified_answers": certified,
        "modern_authenticated_answers": modern_authenticated,
        "legacy_readable_answers": legacy_readable,
        "not_ready_answers": not_ready,
        "failed_ready_answers": failed,
        "recovery_statuses": dict(statuses),
        "release_relationships": dict(release_relationships),
        "issue_codes": dict(issue_codes),
        "failure_findings": failures[:50],
        "failure_findings_omitted": max(0, observed - certified - len(failures)),
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
                if complete
                else "incomplete"
            ),
            "answer_quality": "not_scored",
            "factual_correctness": "not_scored",
            "memory_quality": "not_scored",
        },
        "limitations": [
            "Coverage applies only to durable l_chat_tasks records in the scanned owner history.",
            "A capped or interrupted scan cannot certify full-history recovery coverage.",
            "Legacy readability is not equivalent to modern HMAC authentication.",
            "Recoverability does not establish factual correctness or answer quality.",
            "Malformed records prevent an all-recoverable claim; missing terminal results are recovery failures.",
        ],
    }


def load_recovery_coverage_certification(
    client,
    recovery_token,
    *,
    page_size: int = PAGE_SIZE,
    max_rows: int = MAX_ROWS,
) -> dict:
    rows, scan_complete, capped, scan = scan_task_ledger(
        client, recovery_token, page_size=page_size, max_rows=max_rows,
    )

    report = summarise_recovery_coverage(
        rows,
        scan_complete=scan_complete,
        capped=capped,
    )
    report["scan"] = {
        **scan,
        "in_process_cache_used": False,
    }
    report["claims"]["durable_recovery_coverage_scope"] = scan["scope"]
    report["limitations"].append(
        "Coverage uses a fixed scan-start boundary and keyset pagination; concurrent deletions, backdated inserts, key changes or task updates can still affect this non-transactional scan."
    )
    return report
