"""Layer 114: task-ledger and saved-answer checks over the same durable rows."""

from __future__ import annotations

from core.cognition.durable_task_ledger_audit import (
    MAX_ROWS, PAGE_SIZE, scan_task_ledger, summarise_task_ledger,
)
from core.cognition.recovery_coverage_certification import summarise_recovery_coverage


VERSION = "layer114-durable-recovery-readiness-1"


def summarise_recovery_readiness(
    rows, *, scan_complete: bool, capped: bool, current_release=None, now=None,
) -> dict:
    # Both reports inspect exactly the same materialised observations. Neither
    # report makes a second query or reads the in-process result cache.
    rows = list(rows)
    ledger = summarise_task_ledger(rows, scan_complete=scan_complete, capped=capped, now=now)
    recovery = summarise_recovery_coverage(
        rows, scan_complete=scan_complete, capped=capped, current_release=current_release,
    )
    complete = ledger["scan_complete"] and recovery["scan_complete"]
    ledger_valid = ledger["claims"]["ledger_consistency"] == "verified"
    answers_valid = recovery["coverage"]["all_ready_answers_recoverable"]

    if not complete:
        status = "incomplete_scan"
    elif not ledger_valid or not answers_valid:
        status = "needs_attention"
    elif ledger["tasks_observed"] == 0:
        status = "no_tasks"
    elif recovery["not_ready_answers"]:
        status = "pending_tasks"
    elif recovery["legacy_readable_answers"]:
        status = "ready_with_legacy"
    else:
        status = "ready"

    ready = status in {"ready", "ready_with_legacy"}
    return {
        "version": VERSION,
        "mode": "durable_recovery_readiness",
        "generated_at": recovery["generated_at"],
        "status": status,
        "recovery_ready": ready,
        "scan_complete": complete,
        "capped": bool(capped),
        "checks": {
            "same_observed_rows": True,
            "ledger_consistent": ledger_valid,
            "all_ready_answers_recoverable": answers_valid,
            "all_observed_tasks_certified": recovery["coverage"]["all_observed_tasks_certified"],
            "all_observed_answers_modernly_authenticated": bool(
                ready and recovery["modern_authenticated_answers"] == ledger["tasks_observed"]
            ),
        },
        "task_ledger": ledger,
        "saved_answers": recovery,
        "actions": {
            **ledger["actions"],
            "model_called": False,
            "in_process_cache_used": False,
        },
        "privacy": {
            "request_payloads_returned": False,
            "answer_text_returned": False,
            "raw_request_ids_returned": False,
            "owner_tokens_or_hashes_returned": False,
            "secret_values_returned": False,
        },
        "claims": {
            "recovery_readiness": "verified_for_observed_rows" if ready else "not_verified",
            "transactional_snapshot": False,
            "answer_quality": "not_scored",
            "factual_correctness": "not_scored",
            "task_success": "not_asserted",
        },
        "limitations": [
            "Readiness requires a complete scan, consistent task records and recoverable saved results for every observed task.",
            "Pending or interrupted tasks are not certified as finished; this report never resumes or repairs them.",
            "Legacy readability and provenance compatibility do not imply modern HMAC authentication.",
            "A recoverable failed-task result does not mean the task succeeded.",
            "The shared scan is not a transactional snapshot; concurrent changes can affect coverage or findings.",
            "Recovery checks do not establish factual correctness or answer quality.",
        ],
    }


def load_recovery_readiness(
    client, recovery_token, *, page_size: int = PAGE_SIZE, max_rows: int = MAX_ROWS,
) -> dict:
    rows, complete, capped, scan = scan_task_ledger(
        client, recovery_token, page_size=page_size, max_rows=max_rows,
    )
    report = summarise_recovery_readiness(rows, scan_complete=complete, capped=capped)
    report["scan"] = scan
    report["claims"]["coverage_scope"] = scan["scope"]
    report["limitations"].append(
        "Only tasks created at or before the recorded scan-start boundary are included; later tasks need a new scan."
    )
    return report
