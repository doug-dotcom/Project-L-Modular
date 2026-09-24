"""Layer 116: conservative, owner-scoped signing-key dependency evidence.

An owner's history cannot authorise retirement of a shared signing key.
Known references remain protected even in damaged records; gaps and unknown
references prevent a clean zero-reference assessment. Keys are never changed.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from uuid import UUID

from core.cognition.answer_authenticity import (
    LEGACY_VERSION, VERSION as KEYRING_VERSION, authenticity_status,
)
from core.cognition.durable_task_ledger_audit import scan_task_ledger
from core.cognition.recovery_provenance import verify_recovered_answer_payload


VERSION = "layer116-key-dependency-certification-2"
PAGE_SIZE = 100
MAX_ROWS = 10000
LEGACY_KEY_LABEL = "legacy_layer104"
UNKNOWN_REFERENCE = "unclassified_signed_reference"


def _object(value):
    return value if isinstance(value, dict) else {}


def _raw_auth_dependencies(result: object, known_ids: set[str]) -> tuple[set[str], bool]:
    if not isinstance(result, dict):
        return set(), False
    raw_cognition = result.get("cognition")
    if raw_cognition is not None and not isinstance(raw_cognition, dict):
        return {UNKNOWN_REFERENCE}, True
    cognition = _object(raw_cognition)
    if "answer_authenticity" not in cognition:
        return set(), False
    auth = cognition["answer_authenticity"]
    if not isinstance(auth, dict) or not auth:
        return {UNKNOWN_REFERENCE}, True

    refs = set()
    version = auth.get("version")
    raw_id = auth.get("key_id")
    key_id = raw_id.strip().lower() if isinstance(raw_id, str) else ""
    # Preserve a legacy reference even when a damaged receipt also contains an
    # extra key ID. A conflicting label must never hide the legacy dependency.
    if version == LEGACY_VERSION:
        refs.add(LEGACY_KEY_LABEL)
    if key_id in known_ids:
        refs.add(key_id)
    uncertain = (
        version not in (LEGACY_VERSION, KEYRING_VERSION)
        or (version == KEYRING_VERSION and key_id not in known_ids)
        or (version == LEGACY_VERSION and raw_id not in (None, ""))
    )
    if uncertain:
        refs.add(UNKNOWN_REFERENCE)
    return refs, uncertain


def summarise_key_dependencies(
    rows,
    *,
    scan_complete: bool,
    capped: bool,
    configured_status: dict | None = None,
) -> dict:
    status = dict(authenticity_status() if configured_status is None else configured_status)
    active = str(status.get("active_key_id") or "")
    retained = list(dict.fromkeys(
        key_id for key_id in (status.get("retained_key_ids") or [])
        if isinstance(key_id, str) and key_id
    ))
    known_ids = set(retained) | ({active} if active else set())
    dependencies = Counter()
    verification_states = Counter()
    issue_codes = Counter()
    observed = 0
    malformed = 0
    ready_without_result = 0
    uncertain_rows = 0
    verification_errors = 0
    unverified_answers = 0
    rows_observed = 0

    for row in rows:
        rows_observed += 1
        if not isinstance(row, dict):
            malformed += 1
            uncertain_rows += 1
            issue_codes["malformed_task_row"] += 1
            continue
        result = row.get("result")
        refs, uncertain = _raw_auth_dependencies(result, known_ids)
        dependencies.update(refs)
        if uncertain:
            issue_codes["unclassified_signed_reference"] += 1

        # Inspect dependencies before validating identity: a malformed ID does
        # not erase an otherwise visible reference to a configured key.
        request_id = row.get("request_id")
        try:
            if not isinstance(request_id, str):
                raise ValueError("invalid_id")
            UUID(request_id)
        except ValueError:
            malformed += 1
            uncertain_rows += 1
            issue_codes["request_id_invalid"] += 1
            continue

        observed += 1
        task_status = row.get("status")
        if task_status not in ("queued", "running", "ready", "failed", "interrupted"):
            uncertain = True
            issue_codes["task_status_invalid"] += 1

        if not isinstance(result, dict):
            if row.get("status") == "ready":
                ready_without_result += 1
                issue_codes["ready_without_result"] += 1
            if task_status in ("ready", "failed") or result is not None:
                uncertain = True
                issue_codes["result_missing_or_malformed"] += 1
            verification_states["not_checked"] += 1
            uncertain_rows += int(uncertain)
            continue

        try:
            check = verify_recovered_answer_payload(result, expected_request_id=request_id)
            if not isinstance(check, dict):
                raise TypeError("invalid_verifier_response")
        except Exception:
            verification_errors += 1
            uncertain_rows += 1
            verification_states["verification_error"] += 1
            issue_codes["dependency_verification_error"] += 1
            continue
        if check.get("valid") is not True:
            unverified_answers += 1
            uncertain = True
        uncertain_rows += int(uncertain)
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

    complete = bool(scan_complete and not capped)
    assessed = complete and uncertain_rows == 0

    def decision_for(key_id, is_active=False):
        if is_active:
            return "active_do_not_retire"
        if dependencies.get(key_id, 0):
            return "in_use"
        if not complete:
            return "unknown_incomplete_scan"
        if not assessed:
            return "unknown_unassessed_records"
        return "no_references_in_owner_scope"

    candidates = []
    for key_id in retained:
        refs = int(dependencies.get(key_id, 0))
        decision = decision_for(key_id, key_id == active)
        candidates.append({
            "key_id": key_id,
            "stored_references": refs,
            "decision": decision,
            "automatic_retirement": False,
            "retirement_eligible": False,
        })

    legacy_refs = int(dependencies.get(LEGACY_KEY_LABEL, 0))
    legacy_configured = status.get("legacy_verification_configured") is True
    if legacy_configured:
        legacy_decision = decision_for(LEGACY_KEY_LABEL, not active)
        candidates.append({
            "key_id": LEGACY_KEY_LABEL,
            "stored_references": legacy_refs,
            "decision": legacy_decision,
            "automatic_retirement": False,
            "retirement_eligible": False,
        })

    return {
        "version": VERSION,
        "mode": "signing_key_dependency_certification",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "incomplete" if not complete else "complete_with_uncertainty" if not assessed else "complete",
        "scan_complete": complete,
        "capped": bool(capped),
        "answers_observed": observed,
        "rows_observed": rows_observed,
        "malformed_rows": malformed,
        "malformed_rows_ignored": malformed,
        "uncertain_rows": uncertain_rows,
        "verification_error_rows": verification_errors,
        "unverified_answer_rows": unverified_answers,
        "dependency_assessment_complete": assessed,
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
            "global_dependency_check_required": True,
            "owner_scope_can_authorise_retirement": False,
        },
        "privacy": {
            "answer_text_returned": False,
            "prompt_text_returned": False,
            "evidence_text_returned": False,
            "raw_request_ids_returned": False,
            "secret_values_returned": False,
            "unknown_key_labels_returned": False,
        },
        "claims": {
            "key_dependency_coverage": (
                "complete_for_observed_owner_rows" if assessed else "unverified" if complete else "incomplete"
            ),
            "global_key_dependencies_verified": False,
            "safe_to_auto_retire_any_key": False,
            "answer_quality": "not_scored",
            "factual_correctness": "not_scored",
        },
        "limitations": [
            "Zero references apply only to observed rows for this recovery-token owner; shared-key retirement requires a separate global dependency check.",
            "No key is retired automatically.",
            "A capped or interrupted scan cannot support zero-reference eligibility.",
            "Malformed records, unverifiable answers and unclassified references prevent a complete dependency assessment.",
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
    rows, complete, capped, scan = scan_task_ledger(
        client, recovery_token, page_size=page_size, max_rows=max_rows,
    )
    report = summarise_key_dependencies(rows, scan_complete=complete, capped=capped)
    report["scan"] = scan
    report["claims"]["coverage_scope"] = scan["scope"]
    report["limitations"].append(
        "The bounded keyset scan is not a transactional snapshot; later tasks, external backups and other owners are outside its scope."
    )
    return report
