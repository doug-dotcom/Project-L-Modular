"""Independent Foundation witness for Project L's external-roster head."""

from __future__ import annotations

import re
from typing import Any

import httpx

from services.foundation_trust_witness import (
    _client_token,
    _response_json,
    _witness_url,
)

WITNESS_ID = "foundation-project-l-roster-head"
WITNESS_TYPE = (
    "decision_trace_trust_state_witness_quorum_policy_"
    "external_head_witness_quorum_monotonic_head_witness"
)
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
KEY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


class FoundationRosterHeadWitnessError(RuntimeError):
    pass


def _validate_head(head: Any) -> dict[str, Any]:
    if not isinstance(head, dict):
        raise FoundationRosterHeadWitnessError(
            "foundation-roster-head-invalid"
        )
    sequence = head.get("sequence")
    generation = head.get("generation")
    hashes = (
        head.get("headSha256"),
        head.get("policySha256"),
        head.get("stateSha256"),
    )
    if (
        head.get("headVersion") != 1
        or not isinstance(sequence, int)
        or isinstance(sequence, bool)
        or not 1 <= sequence <= 1_000_000
        or not isinstance(generation, int)
        or isinstance(generation, bool)
        or generation != sequence
        or any(
            not isinstance(value, str)
            or SHA256_RE.fullmatch(value) is None
            for value in hashes
        )
    ):
        raise FoundationRosterHeadWitnessError(
            "foundation-roster-head-invalid"
        )
    return head


def _safe_receipt(data: Any, head: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise FoundationRosterHeadWitnessError(
            "foundation-roster-head-witness-response-invalid"
        )
    key_id = data.get("authKeyId")
    auth_tag = data.get("authTag")
    if (
        data.get("status") != "witnessed"
        or data.get("witnessVersion") != 1
        or data.get("witnessType") != WITNESS_TYPE
        or data.get("authAlgorithm") != "HMAC-SHA-256"
        or data.get("witnessId") != WITNESS_ID
        or not isinstance(key_id, str)
        or KEY_ID_RE.fullmatch(key_id) is None
        or data.get("headVersion") != 1
        or data.get("sequence") != head["sequence"]
        or data.get("headSha256") != head["headSha256"]
        or data.get("generation") != head["generation"]
        or data.get("policySha256") != head["policySha256"]
        or data.get("stateSha256") != head["stateSha256"]
        or not isinstance(auth_tag, str)
        or SHA256_RE.fullmatch(auth_tag) is None
    ):
        raise FoundationRosterHeadWitnessError(
            "foundation-roster-head-witness-response-invalid"
        )
    return {
        "status": "verified",
        "witness_id": WITNESS_ID,
        "auth_key_id": key_id,
        "sequence": head["sequence"],
        "head_sha256": head["headSha256"],
        "generation": head["generation"],
        "policy_sha256": head["policySha256"],
        "state_sha256": head["stateSha256"],
        "replayed": data.get("replayed") is True,
        "independent_retention": "foundation-supabase-vault-hmac",
    }


def ensure_foundation_roster_head_witness(
    db,
    head: Any,
    *,
    witness_url: str | None = None,
    timeout_seconds: float = 4.0,
    post_impl=None,
) -> dict[str, Any]:
    projected = _validate_head(head)
    token = _client_token(db)
    post = post_impl or httpx.post
    payload = {
        "operation": "external-roster-head-record",
        "witnessId": WITNESS_ID,
        "sequence": projected["sequence"],
        "headSha256": projected["headSha256"],
        "generation": projected["generation"],
        "policySha256": projected["policySha256"],
        "stateSha256": projected["stateSha256"],
    }
    try:
        response = post(
            _witness_url(witness_url),
            headers={
                "X-Shine-Client-Token": token,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout_seconds,
            follow_redirects=False,
        )
        data = _response_json(response)
    except FoundationRosterHeadWitnessError:
        raise
    except Exception as exc:
        raise FoundationRosterHeadWitnessError(
            "foundation-roster-head-witness-unavailable"
        ) from exc
    if int(response.status_code) >= 400:
        raise FoundationRosterHeadWitnessError(
            str(
                data.get("reasonCode")
                or "foundation-roster-head-witness-rejected"
            )
        )
    return _safe_receipt(data, projected)


def current_foundation_roster_head_witness(
    db,
    *,
    witness_url: str | None = None,
    timeout_seconds: float = 4.0,
    post_impl=None,
) -> dict[str, Any] | None:
    token = _client_token(db)
    post = post_impl or httpx.post
    try:
        response = post(
            _witness_url(witness_url),
            headers={
                "X-Shine-Client-Token": token,
                "Content-Type": "application/json",
            },
            json={
                "operation": "external-roster-head-current",
                "witnessId": WITNESS_ID,
            },
            timeout=timeout_seconds,
            follow_redirects=False,
        )
        data = _response_json(response)
    except Exception as exc:
        raise FoundationRosterHeadWitnessError(
            "foundation-roster-head-witness-unavailable"
        ) from exc
    if int(response.status_code) >= 400:
        raise FoundationRosterHeadWitnessError(
            str(
                data.get("reasonCode")
                or "foundation-roster-head-witness-rejected"
            )
        )
    if data.get("status") == "empty":
        return None
    head = {
        "headVersion": data.get("headVersion"),
        "sequence": data.get("sequence"),
        "headSha256": data.get("headSha256"),
        "generation": data.get("generation"),
        "policySha256": data.get("policySha256"),
        "stateSha256": data.get("stateSha256"),
    }
    return _safe_receipt(data, _validate_head(head))



def rotate_foundation_roster_head_witness(
    db,
    target_auth_key_id: str,
    *,
    witness_url: str | None = None,
    timeout_seconds: float = 4.0,
    post_impl=None,
) -> dict[str, Any]:
    if (
        not isinstance(target_auth_key_id, str)
        or KEY_ID_RE.fullmatch(target_auth_key_id) is None
    ):
        raise FoundationRosterHeadWitnessError(
            "foundation-roster-head-witness-rotation-target-invalid"
        )

    before = current_foundation_roster_head_witness(
        db,
        witness_url=witness_url,
        timeout_seconds=timeout_seconds,
        post_impl=post_impl,
    )
    if before is None:
        raise FoundationRosterHeadWitnessError(
            "foundation-roster-head-witness-rotation-source-missing"
        )

    if before["auth_key_id"] == target_auth_key_id:
        return {
            "status": "verified",
            "mode": "already-rotated",
            "source_auth_key_id": before["auth_key_id"],
            "target_auth_key_id": target_auth_key_id,
            "sequence": before["sequence"],
            "head_sha256": before["head_sha256"],
            "generation": before["generation"],
            "policy_sha256": before["policy_sha256"],
            "state_sha256": before["state_sha256"],
            "state_preserved": True,
            "witness": before,
        }

    token = _client_token(db)
    post = post_impl or httpx.post
    try:
        response = post(
            _witness_url(witness_url),
            headers={
                "X-Shine-Client-Token": token,
                "Content-Type": "application/json",
            },
            json={
                "operation": "external-roster-head-rotate",
                "witnessId": WITNESS_ID,
                "targetAuthKeyId": target_auth_key_id,
            },
            timeout=timeout_seconds,
            follow_redirects=False,
        )
        data = _response_json(response)
    except Exception as exc:
        raise FoundationRosterHeadWitnessError(
            "foundation-roster-head-witness-rotation-unavailable"
        ) from exc

    if int(response.status_code) >= 400:
        raise FoundationRosterHeadWitnessError(
            str(
                data.get("reasonCode")
                or "foundation-roster-head-witness-rotation-rejected"
            )
        )

    receipt = data.get("receipt")
    witness = data.get("witness")
    if (
        data.get("status") != "rotated"
        or not isinstance(receipt, dict)
        or not isinstance(witness, dict)
        or receipt.get("version") != 1
        or receipt.get("eventType")
        != (
            "decision_trace_trust_state_witness_quorum_policy_"
            "monotonic_head_witness_key_rotation"
        )
        or receipt.get("witnessId") != WITNESS_ID
        or receipt.get("sourceAuthKeyId") != before["auth_key_id"]
        or receipt.get("targetAuthKeyId") != target_auth_key_id
        or receipt.get("sequence") != before["sequence"]
        or receipt.get("headSha256") != before["head_sha256"]
        or receipt.get("generation") != before["generation"]
        or receipt.get("policySha256") != before["policy_sha256"]
        or receipt.get("stateSha256") != before["state_sha256"]
    ):
        raise FoundationRosterHeadWitnessError(
            "foundation-roster-head-witness-rotation-response-invalid"
        )

    expected_head = {
        "headVersion": 1,
        "sequence": before["sequence"],
        "headSha256": before["head_sha256"],
        "generation": before["generation"],
        "policySha256": before["policy_sha256"],
        "stateSha256": before["state_sha256"],
    }
    rotated = _safe_receipt(witness, _validate_head(expected_head))
    if rotated["auth_key_id"] != target_auth_key_id:
        raise FoundationRosterHeadWitnessError(
            "foundation-roster-head-witness-rotation-target-mismatch"
        )

    after = current_foundation_roster_head_witness(
        db,
        witness_url=witness_url,
        timeout_seconds=timeout_seconds,
        post_impl=post_impl,
    )
    if (
        after is None
        or after["auth_key_id"] != target_auth_key_id
        or any(
            after[key] != before[key]
            for key in (
                "witness_id",
                "sequence",
                "head_sha256",
                "generation",
                "policy_sha256",
                "state_sha256",
            )
        )
    ):
        raise FoundationRosterHeadWitnessError(
            "foundation-roster-head-witness-rotation-persistence-invalid"
        )

    return {
        "status": "verified",
        "mode": "rotated",
        "source_auth_key_id": before["auth_key_id"],
        "target_auth_key_id": target_auth_key_id,
        "sequence": after["sequence"],
        "head_sha256": after["head_sha256"],
        "generation": after["generation"],
        "policy_sha256": after["policy_sha256"],
        "state_sha256": after["state_sha256"],
        "state_preserved": True,
        "witness": after,
    }


__all__ = [
    "FoundationRosterHeadWitnessError",
    "WITNESS_ID",
    "WITNESS_TYPE",
    "current_foundation_roster_head_witness",
    "ensure_foundation_roster_head_witness",
    "rotate_foundation_roster_head_witness",
]
