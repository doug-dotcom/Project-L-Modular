"""Layer 106: owner-scoped, read-only saved-answer integrity audit.

The audit verifies saved production answers without replaying tasks or returning
answer text. It reports aggregate delivery/provenance/authenticity states and
privacy-safe issue references only.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256

from core.cognition.durable_tasks import owner_identity
from core.cognition.recovery_provenance import (
    PROTOCOL_KEY,
    verify_recovered_answer_payload,
)


VERSION = "layer106-saved-answer-integrity-audit-1"
MAX_LIMIT = 100


def _object(value):
    return value if isinstance(value, dict) else {}


def _safe_request_ref(request_id: str) -> str:
    return sha256(str(request_id).encode("utf-8")).hexdigest()[:12]


def summarise_saved_answer_integrity(rows) -> dict:
    delivery_states = Counter()
    recovery_states = Counter()
    protocol_states = Counter()
    release_commits = Counter()
    authenticity_keys = Counter()
    issue_codes = Counter()
    findings = []
    seen = set()
    duplicates = malformed = 0

    for row in rows:
        if not isinstance(row, dict):
            malformed += 1
            continue
        request_id = row.get("request_id")
        if not isinstance(request_id, str) or not request_id:
            malformed += 1
            continue
        if request_id in seen:
            duplicates += 1
            continue
        seen.add(request_id)

        result = row.get("result")
        if not isinstance(result, dict):
            delivery_states["no_result"] += 1
            recovery_states["not_checked"] += 1
            if row.get("status") == "ready":
                issue_codes["ready_without_result"] += 1
                findings.append({
                    "request_ref": _safe_request_ref(request_id),
                    "status": "ready_without_result",
                    "issues": ["ready_without_result"],
                })
            continue

        check = verify_recovered_answer_payload(
            result,
            expected_request_id=request_id,
        )
        delivery = _object(check.get("delivery_integrity"))
        if delivery.get("valid") and delivery.get("bound"):
            delivery_states["verified_bound"] += 1
        elif delivery.get("valid"):
            delivery_states["legacy_unbound"] += 1
        else:
            delivery_states["invalid"] += 1

        recovery_status = str(check.get("status") or "unknown")[:80]
        recovery_states[recovery_status] += 1

        protocol = result.get(PROTOCOL_KEY)
        protocol_states[str(protocol or "none")[:40]] += 1

        cognition = _object(result.get("cognition"))
        provenance = _object(cognition.get("answer_provenance"))
        if check.get("valid"):
            commit = str(provenance.get("release_commit_sha") or "")
            if commit:
                release_commits[commit[:40]] += 1

            auth = _object(check.get("answer_authenticity"))
            mode = str(auth.get("verification_mode") or "")
            key_id = str(auth.get("key_id") or "")
            if mode == "keyring" and key_id:
                authenticity_keys[key_id[:32]] += 1
            elif mode == "legacy_layer104":
                authenticity_keys["legacy_layer104"] += 1
            elif check.get("authenticity_required"):
                authenticity_keys["required_unclassified"] += 1
            else:
                authenticity_keys["unsigned_legacy"] += 1

        issues = [
            str(issue)[:120]
            for issue in (check.get("issues") or [])
            if isinstance(issue, str)
        ]
        auth_issues = [
            str(issue)[:120]
            for issue in (_object(check.get("answer_authenticity")).get("issues") or [])
            if isinstance(issue, str)
        ]
        provenance_issues = [
            str(issue)[:120]
            for issue in (_object(check.get("answer_provenance")).get("issues") or [])
            if isinstance(issue, str)
        ]
        all_issues = []
        for issue in issues + auth_issues + provenance_issues:
            if issue not in all_issues:
                all_issues.append(issue)
                issue_codes[issue] += 1

        if not check.get("valid"):
            findings.append({
                "request_ref": _safe_request_ref(request_id),
                "status": recovery_status,
                "issues": all_issues[:12],
            })

    observed = len(seen)
    invalid = sum(
        count for status, count in recovery_states.items()
        if status in {"invalid", "invalid_delivery"}
    )
    v2_total = protocol_states.get("2.0", 0)
    v2_authenticated = recovery_states.get("verified_authentic_production", 0)
    legacy_total = observed - v2_total

    return {
        "version": VERSION,
        "mode": "saved_answer_integrity_audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "observed" if observed else "no_data",
        "answers_observed": observed,
        "duplicate_rows_ignored": duplicates,
        "malformed_rows_ignored": malformed,
        "delivery_integrity": dict(delivery_states),
        "recovery_integrity": dict(recovery_states),
        "protocol_versions": dict(protocol_states),
        "release_commits": dict(release_commits),
        "answer_authenticity_keys": dict(authenticity_keys),
        "issue_codes": dict(issue_codes),
        "invalid_answers": invalid,
        "current_protocol": {
            "version": "2.0",
            "observed": v2_total,
            "verified_authentic_production": v2_authenticated,
            "other_or_invalid": max(0, v2_total - v2_authenticated),
        },
        "legacy_answers_observed": max(0, legacy_total),
        "findings": findings[:25],
        "privacy": {
            "answer_text_returned": False,
            "prompt_text_returned": False,
            "evidence_text_returned": False,
            "raw_request_ids_returned": False,
            "request_refs": "sha256_prefix_12",
            "secret_values_returned": False,
        },
        "key_retirement": {
            "decision": "not_automated",
            "observed_key_references": dict(authenticity_keys),
            "note": (
                "Observed counts support rotation review only. "
                "Absence from a bounded sample is not proof that a historical key is safe to retire."
            ),
        },
        "claims": {
            "stored_payload_integrity": "measured",
            "answer_quality": "not_scored",
            "factual_correctness": "not_scored",
            "memory_quality": "not_scored",
        },
        "limitations": [
            "The audit is read-only and does not replay tasks or call a model.",
            "A bounded recent sample is not proof that no older records use a key.",
            "Legacy answers may be readable without modern provenance or HMAC receipts.",
            "Integrity and authenticity do not establish factual correctness or answer quality.",
        ],
    }


def load_saved_answer_integrity_audit(client, recovery_token, limit=50) -> dict:
    if type(limit) is not int or not 1 <= limit <= MAX_LIMIT:
        raise ValueError("Choose between 1 and 100 tasks")
    user_id, owner_hash = owner_identity(recovery_token)
    if client is None:
        raise RuntimeError("database_unavailable")

    rows = (
        client.table("l_chat_tasks")
        .select("request_id,created_at,status,result")
        .eq("user_id", user_id)
        .eq("owner_hash", owner_hash)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data
    )
    if not isinstance(rows, list):
        raise RuntimeError("invalid_database_response")

    report = summarise_saved_answer_integrity(rows)
    report["sample"] = {
        "scope": "recovery_token_owner",
        "order": "newest_first",
        "limit": limit,
        "read_only": True,
    }
    return report
