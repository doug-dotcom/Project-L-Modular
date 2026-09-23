"""Layer 101: privacy-safe production provenance attestation.

The receipt is built only from Railway's non-secret runtime identity metadata.
It proves what the running container reports about its source/environment; it
does not prove answer quality, human acceptance, or that a GitHub commit is good.
"""

from __future__ import annotations

from hashlib import sha256
import json
import os
import re


VERSION = "layer101-production-provenance-1"
EXPECTED_REPOSITORY = "doug-dotcom/Project-L-Modular"
EXPECTED_BRANCH = "main"
EXPECTED_SERVICE = "Project-L-Modular"
EXPECTED_ENVIRONMENT = "production"

SAFE_ENV_FIELDS = {
    "repository_owner": "RAILWAY_GIT_REPO_OWNER",
    "repository_name": "RAILWAY_GIT_REPO_NAME",
    "branch": "RAILWAY_GIT_BRANCH",
    "commit_sha": "RAILWAY_GIT_COMMIT_SHA",
    "project_name": "RAILWAY_PROJECT_NAME",
    "service_name": "RAILWAY_SERVICE_NAME",
    "environment_name": "RAILWAY_ENVIRONMENT_NAME",
}


def _canonical_sha256(value: dict) -> str:
    return sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _safe_value(value: object, limit: int = 160) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text[:limit]


def build_release_provenance(environ: dict | None = None) -> dict:
    env = os.environ if environ is None else environ
    identity = {
        field: _safe_value(env.get(name))
        for field, name in SAFE_ENV_FIELDS.items()
    }
    repository = (
        f"{identity['repository_owner']}/{identity['repository_name']}"
        if identity["repository_owner"] and identity["repository_name"]
        else ""
    )
    commit_sha = identity["commit_sha"].lower()
    commit_valid = bool(re.fullmatch(r"[0-9a-f]{40}", commit_sha))
    complete = bool(
        repository
        and identity["branch"]
        and commit_valid
        and identity["service_name"]
        and identity["environment_name"]
    )
    production_match = bool(
        complete
        and repository == EXPECTED_REPOSITORY
        and identity["branch"] == EXPECTED_BRANCH
        and identity["service_name"] == EXPECTED_SERVICE
        and identity["environment_name"] == EXPECTED_ENVIRONMENT
    )

    receipt = {
        "version": VERSION,
        "status": (
            "verified_production"
            if production_match
            else "metadata_mismatch"
            if complete
            else "unavailable"
        ),
        "verified": production_match,
        "repository": repository,
        "branch": identity["branch"],
        "commit_sha": commit_sha if commit_valid else "",
        "project_name": identity["project_name"],
        "service_name": identity["service_name"],
        "environment_name": identity["environment_name"],
        "metadata_complete": complete,
        "commit_sha_valid": commit_valid,
        "expected": {
            "repository": EXPECTED_REPOSITORY,
            "branch": EXPECTED_BRANCH,
            "service_name": EXPECTED_SERVICE,
            "environment_name": EXPECTED_ENVIRONMENT,
        },
        "claims": {
            "running_source_identity": (
                "verified" if production_match else "not_verified"
            ),
            "commit_quality": "not_asserted",
            "deployment_health": "not_asserted",
            "answer_quality": "not_asserted",
            "human_acceptance": "not_asserted",
        },
    }
    receipt["receipt_sha256"] = _canonical_sha256(receipt)
    return receipt


def verify_release_provenance(receipt: dict | None) -> dict:
    if not isinstance(receipt, dict):
        return {
            "version": VERSION,
            "valid": False,
            "issues": ["provenance_receipt_missing_or_malformed"],
        }

    payload = dict(receipt)
    declared = _safe_value(payload.pop("receipt_sha256", ""))
    issues = []
    if not re.fullmatch(r"[0-9a-f]{64}", declared):
        issues.append("provenance_receipt_hash_invalid")
    elif declared != _canonical_sha256(payload):
        issues.append("provenance_receipt_hash_mismatch")

    commit_sha = _safe_value(receipt.get("commit_sha")).lower()
    if commit_sha and not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
        issues.append("provenance_commit_sha_invalid")

    if receipt.get("verified") is True:
        if receipt.get("status") != "verified_production":
            issues.append("provenance_verified_status_mismatch")
        if receipt.get("repository") != EXPECTED_REPOSITORY:
            issues.append("provenance_repository_mismatch")
        if receipt.get("branch") != EXPECTED_BRANCH:
            issues.append("provenance_branch_mismatch")
        if receipt.get("service_name") != EXPECTED_SERVICE:
            issues.append("provenance_service_mismatch")
        if receipt.get("environment_name") != EXPECTED_ENVIRONMENT:
            issues.append("provenance_environment_mismatch")
        if not re.fullmatch(r"[0-9a-f]{40}", commit_sha):
            issues.append("provenance_commit_sha_missing")

    return {
        "version": VERSION,
        "valid": not issues,
        "verified_production": bool(
            not issues and receipt.get("verified") is True
        ),
        "issues": issues,
        "receipt_sha256": declared,
        "commit_sha": commit_sha if not issues else "",
    }
