"""Layer 107: production cryptographic readiness gate.

Railway already health-checks /health. This gate makes that check meaningful for
answer provenance security: verified production must prove its signing keyring
can sign and verify before a release is considered healthy.
"""

from __future__ import annotations

import json
import os
import re

from core.cognition.answer_authenticity import (
    ACTIVE_KEY_ID_ENV,
    VERIFY_KEY_IDS_ENV,
    VERSION as AUTHENTICITY_VERSION,
    authenticity_status,
    sign_answer_provenance,
    verify_answer_authenticity,
)
from core.cognition.release_provenance import build_release_provenance


VERSION = "layer107-production-security-gate-1"
RELEASE_LAYER = 107


def _explicit_verify_ids(environ: dict) -> list[str]:
    raw = str(environ.get(VERIFY_KEY_IDS_ENV, "") or "")
    ids: list[str] = []
    for part in raw.split(","):
        key_id = part.strip().lower()
        if re.fullmatch(r"[a-z0-9][a-z0-9-]{0,31}", key_id) and key_id not in ids:
            ids.append(key_id)
    return ids[:16]


def production_security_gate(environ: dict | None = None) -> dict:
    env = os.environ if environ is None else environ
    release = build_release_provenance(env)
    auth = authenticity_status(environ=env)
    production_enforced = bool(
        release.get("verified") is True
        and release.get("status") == "verified_production"
    )

    checks = {
        "verified_production_identity": production_enforced,
        "keyring_mode": auth.get("mode") == "keyring",
        "active_key_id_present": bool(auth.get("active_key_id")),
        "active_key_configured": auth.get("active_key_configured") is True,
        "legacy_verification_configured": auth.get("legacy_verification_configured") is True,
        "secret_exposed": auth.get("secret_exposed") is True,
    }

    explicit_verify_ids = _explicit_verify_ids(env)
    active_key_id = str(auth.get("active_key_id") or "")
    checks["active_key_explicitly_retained"] = bool(
        active_key_id and active_key_id in explicit_verify_ids
    )

    self_test = {
        "attempted": False,
        "signed": False,
        "verified": False,
        "receipt_version": "",
        "key_id": "",
        "issues": [],
    }

    if production_enforced:
        synthetic_provenance = {
            "version": "layer107-synthetic-answer-provenance",
            "release_layer": RELEASE_LAYER,
            "request_id": "layer107-production-security-self-test",
            "reply_sha256": "a" * 64,
            "release_commit_sha": str(release.get("commit_sha") or ""),
            "release_provenance_receipt_sha256": str(release.get("receipt_sha256") or ""),
            "response_model_receipt_sha256": "b" * 64,
            "context_budget_receipt_sha256": "c" * 64,
            "assistant_persistence_receipt_sha256": "d" * 64,
            "claims": {"synthetic_self_test": True},
            "receipt_sha256": "e" * 64,
        }
        signed = sign_answer_provenance(
            synthetic_provenance,
            environ=env,
        )
        verified = verify_answer_authenticity(
            signed,
            synthetic_provenance,
            environ=env,
        )
        self_test = {
            "attempted": True,
            "signed": signed.get("valid") is True,
            "verified": verified.get("valid") is True and verified.get("authentic") is True,
            "receipt_version": str(signed.get("version") or ""),
            "key_id": str(signed.get("key_id") or ""),
            "issues": list(dict.fromkeys(
                [
                    str(issue)
                    for issue in (
                        list(signed.get("issues") or [])
                        + list(verified.get("issues") or [])
                    )
                    if isinstance(issue, str)
                ]
            ))[:12],
        }

    issues: list[str] = []
    if production_enforced:
        required = {
            "keyring_mode": "production_keyring_mode_required",
            "active_key_id_present": "production_active_key_id_required",
            "active_key_configured": "production_active_key_secret_required",
            "active_key_explicitly_retained": "production_active_key_must_be_in_verify_list",
            "legacy_verification_configured": "production_legacy_verification_key_required",
        }
        for field, issue in required.items():
            if not checks.get(field):
                issues.append(issue)
        if checks["secret_exposed"]:
            issues.append("production_authenticity_status_exposed_secret")
        if not self_test["signed"]:
            issues.append("production_signing_self_test_failed")
        if not self_test["verified"]:
            issues.append("production_verification_self_test_failed")
        if self_test["receipt_version"] != AUTHENTICITY_VERSION:
            issues.append("production_signing_receipt_version_mismatch")
        if self_test["key_id"] != active_key_id:
            issues.append("production_signing_key_id_mismatch")
        for issue in self_test["issues"]:
            if issue not in issues:
                issues.append(issue)

    ready = (not production_enforced) or not issues
    status = (
        "ready"
        if production_enforced and ready
        else "blocked"
        if production_enforced
        else "not_enforced_nonproduction"
    )

    report = {
        "version": VERSION,
        "release_layer": RELEASE_LAYER,
        "status": status,
        "ready": ready,
        "production_enforced": production_enforced,
        "release_commit_sha": str(release.get("commit_sha") or ""),
        "active_key_id": active_key_id,
        "explicit_verify_key_ids": explicit_verify_ids,
        "retained_key_ids": list(auth.get("retained_key_ids") or []),
        "checks": checks,
        "self_test": self_test,
        "issues": issues,
        "privacy": {
            "secret_values_returned": False,
            "signatures_returned": False,
            "answer_text_used": False,
            "private_memory_used": False,
        },
        "claims": {
            "production_keyring_operational": (
                "verified" if production_enforced and ready else "not_verified"
            ),
            "answer_quality": "not_asserted",
            "factual_correctness": "not_asserted",
            "memory_quality": "not_asserted",
        },
    }

    # Defensive invariant: no environment secret values may appear in the report.
    serialised = json.dumps(report, sort_keys=True)
    for name, value in env.items():
        if (
            isinstance(name, str)
            and name.startswith("L_ANSWER_PROVENANCE_SIGNING_KEY")
            and isinstance(value, str)
            and value
            and value in serialised
        ):
            report["ready"] = False
            report["status"] = "blocked" if production_enforced else "not_enforced_nonproduction"
            report["issues"] = list(dict.fromkeys(
                report["issues"] + ["production_security_report_secret_leak"]
            ))
            break

    return report
