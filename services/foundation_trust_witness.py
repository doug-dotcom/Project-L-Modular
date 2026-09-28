"""Independent Foundation witness for Project L's monotonic trust head."""

from __future__ import annotations

import os
import re
from typing import Any

import httpx

from services.shine_trust_storage import (
    TrustStorageError,
    prepare_monotonic_head,
)

DEFAULT_FOUNDATION_WITNESS_URL = (
    "https://sjpxqeyewahraxvidvcc.supabase.co/functions/v1/"
    "project-l-trust-witness"
)
WITNESS_ID = "foundation-project-l"
ROSTER_HEAD_WITNESS_ID = "foundation-project-l-roster-head"
ROSTER_HEAD_WITNESS_TYPE = (
    "decision_trace_trust_state_witness_quorum_policy_"
    "external_head_witness_quorum_monotonic_head_witness"
)
MAX_RESPONSE_BYTES = 32 * 1024
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
CHAIN_VERSION = 1
GENESIS_CHAIN_TAG = "0" * 64


class FoundationWitnessError(RuntimeError):
    pass


def _single_secret(value: Any) -> str:
    if not isinstance(value, str) or len(value) < 32 or len(value) > 8192:
        raise FoundationWitnessError("foundation-witness-client-token-unavailable")
    return value


def _client_token(db) -> str:
    try:
        result = db.rpc("concierge_foundation_client_token_v1", {}).execute()
    except Exception as exc:
        raise FoundationWitnessError(
            "foundation-witness-client-token-unavailable"
        ) from exc
    return _single_secret(getattr(result, "data", None))


def _witness_url(value: str | None = None) -> str:
    url = str(
        value
        or os.getenv("SHINE_FOUNDATION_WITNESS_URL")
        or DEFAULT_FOUNDATION_WITNESS_URL
    ).strip().rstrip("/")
    if not url.startswith("https://"):
        raise FoundationWitnessError("foundation-witness-url-invalid")
    return url


def _response_json(response) -> dict:
    declared = (
        response.headers.get("content-length")
        if hasattr(response, "headers")
        else None
    )
    try:
        if declared is not None and int(declared) > MAX_RESPONSE_BYTES:
            raise FoundationWitnessError("foundation-witness-response-too-large")
    except (TypeError, ValueError):
        pass
    raw = bytes(getattr(response, "content", b""))
    if len(raw) > MAX_RESPONSE_BYTES:
        raise FoundationWitnessError("foundation-witness-response-too-large")
    try:
        data = response.json()
    except Exception as exc:
        raise FoundationWitnessError(
            "foundation-witness-response-invalid"
        ) from exc
    if not isinstance(data, dict):
        raise FoundationWitnessError("foundation-witness-response-invalid")
    return data


def _current_witness(
    db,
    *,
    witness_url: str | None = None,
    timeout_seconds: float = 4.0,
    get_impl=None,
) -> dict:
    token = _client_token(db)
    get = get_impl or httpx.get
    try:
        response = get(
            _witness_url(witness_url),
            headers={"X-Shine-Client-Token": token},
            params={"witnessId": WITNESS_ID},
            timeout=timeout_seconds,
            follow_redirects=False,
        )
        data = _response_json(response)
    except FoundationWitnessError:
        raise
    except Exception as exc:
        raise FoundationWitnessError(
            "foundation-witness-unavailable"
        ) from exc
    if int(response.status_code) >= 400:
        raise FoundationWitnessError(
            str(data.get("reasonCode") or "foundation-witness-rejected")
        )
    return data


def _record_witness(
    db,
    head: dict,
    *,
    witness_url: str | None = None,
    timeout_seconds: float = 4.0,
    post_impl=None,
) -> dict:
    token = _client_token(db)
    post = post_impl or httpx.post
    payload = {
        "witnessId": WITNESS_ID,
        "sequence": head["sequence"],
        "headSha256": head["headSha256"],
        "generation": head["generation"],
        "keyset_sha256": head["keyset_sha256"],
        "stateSha256": head["stateSha256"],
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
    except FoundationWitnessError:
        raise
    except Exception as exc:
        raise FoundationWitnessError(
            "foundation-witness-unavailable"
        ) from exc
    if int(response.status_code) >= 400:
        raise FoundationWitnessError(
            str(data.get("reasonCode") or "foundation-witness-rejected")
        )
    return data



def _current_roster_head_witness(
    db,
    *,
    witness_url: str | None = None,
    timeout_seconds: float = 4.0,
    get_impl=None,
) -> dict:
    token = _client_token(db)
    get = get_impl or httpx.get
    try:
        response = get(
            _witness_url(witness_url),
            headers={"X-Shine-Client-Token": token},
            params={
                "scope": "external-roster-head",
                "witnessId": ROSTER_HEAD_WITNESS_ID,
            },
            timeout=timeout_seconds,
            follow_redirects=False,
        )
        data = _response_json(response)
    except FoundationWitnessError:
        raise
    except Exception as exc:
        raise FoundationWitnessError(
            "foundation-roster-head-witness-unavailable"
        ) from exc
    if int(response.status_code) >= 400:
        raise FoundationWitnessError(
            str(
                data.get("reasonCode")
                or "foundation-roster-head-witness-rejected"
            )
        )
    return data


def _record_roster_head_witness(
    db,
    head: dict,
    *,
    witness_url: str | None = None,
    timeout_seconds: float = 4.0,
    post_impl=None,
) -> dict:
    token = _client_token(db)
    post = post_impl or httpx.post
    payload = {
        "scope": "external-roster-head",
        "witnessId": ROSTER_HEAD_WITNESS_ID,
        "sequence": head["sequence"],
        "headSha256": head["headSha256"],
        "generation": head["generation"],
        "policySha256": head["policySha256"],
        "stateSha256": head["stateSha256"],
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
    except FoundationWitnessError:
        raise
    except Exception as exc:
        raise FoundationWitnessError(
            "foundation-roster-head-witness-unavailable"
        ) from exc
    if int(response.status_code) >= 400:
        raise FoundationWitnessError(
            str(
                data.get("reasonCode")
                or "foundation-roster-head-witness-rejected"
            )
        )
    return data


def _roster_head_witness_projection(value: Any) -> dict:
    if not isinstance(value, dict):
        raise FoundationWitnessError(
            "foundation-roster-head-witness-response-invalid"
        )
    if value.get("status") != "witnessed":
        raise FoundationWitnessError(
            str(
                value.get("reasonCode")
                or "foundation-roster-head-witness-response-invalid"
            )
        )
    result = {
        "witness_id": value.get("witnessId"),
        "auth_key_id": value.get("authKeyId"),
        "sequence": value.get("sequence"),
        "head_sha256": value.get("headSha256"),
        "generation": value.get("generation"),
        "policy_sha256": value.get("policySha256"),
        "state_sha256": value.get("stateSha256"),
        "auth_tag": value.get("authTag"),
    }
    if (
        value.get("witnessVersion") != 1
        or value.get("witnessType") != ROSTER_HEAD_WITNESS_TYPE
        or value.get("authAlgorithm") != "HMAC-SHA-256"
        or value.get("headVersion") != 1
        or result["witness_id"] != ROSTER_HEAD_WITNESS_ID
        or not isinstance(result["auth_key_id"], str)
        or not result["auth_key_id"]
        or not isinstance(result["sequence"], int)
        or result["sequence"] < 1
        or not isinstance(result["generation"], int)
        or result["generation"] < 1
        or any(
            not isinstance(result[key], str)
            or SHA256_RE.fullmatch(result[key]) is None
            for key in (
                "head_sha256",
                "policy_sha256",
                "state_sha256",
                "auth_tag",
            )
        )
    ):
        raise FoundationWitnessError(
            "foundation-roster-head-witness-response-invalid"
        )
    return result


def _roster_head_matches(witness: dict, head: dict) -> bool:
    return (
        witness["sequence"] == head["sequence"]
        and witness["head_sha256"] == head["headSha256"]
        and witness["generation"] == head["generation"]
        and witness["policy_sha256"] == head["policySha256"]
        and witness["state_sha256"] == head["stateSha256"]
    )


def ensure_foundation_roster_head_witness(
    db,
    head: dict,
    *,
    witness_url: str | None = None,
    timeout_seconds: float = 4.0,
    get_impl=None,
    post_impl=None,
) -> dict:
    current_raw = _current_roster_head_witness(
        db,
        witness_url=witness_url,
        timeout_seconds=timeout_seconds,
        get_impl=get_impl,
    )
    status = str(current_raw.get("status") or "")

    if status == "empty":
        if head.get("sequence") != 1 or head.get("generation") != 1:
            raise FoundationWitnessError(
                "foundation-roster-head-witness-history-missing"
            )
        recorded = _roster_head_witness_projection(
            _record_roster_head_witness(
                db,
                head,
                witness_url=witness_url,
                timeout_seconds=timeout_seconds,
                post_impl=post_impl,
            )
        )
        if not _roster_head_matches(recorded, head):
            raise FoundationWitnessError(
                "foundation-roster-head-witness-commit-mismatch"
            )
        return {
            "status": "verified",
            **recorded,
            "mode": "created",
            "independent_retention": "foundation-supabase",
        }

    current = _roster_head_witness_projection(current_raw)
    if _roster_head_matches(current, head):
        return {
            "status": "verified",
            **current,
            "mode": "existing-witness",
            "independent_retention": "foundation-supabase",
        }

    if current["sequence"] > head.get("sequence", 0):
        raise FoundationWitnessError(
            "foundation-roster-head-witness-ahead"
        )
    if current["sequence"] == head.get("sequence"):
        raise FoundationWitnessError(
            "foundation-roster-head-witness-fork"
        )
    if head.get("sequence") != current["sequence"] + 1:
        raise FoundationWitnessError(
            "foundation-roster-head-witness-sequence-gap"
        )

    recorded = _roster_head_witness_projection(
        _record_roster_head_witness(
            db,
            head,
            witness_url=witness_url,
            timeout_seconds=timeout_seconds,
            post_impl=post_impl,
        )
    )
    if not _roster_head_matches(recorded, head):
        raise FoundationWitnessError(
            "foundation-roster-head-witness-commit-mismatch"
        )
    return {
        "status": "verified",
        **recorded,
        "mode": "advanced",
        "independent_retention": "foundation-supabase",
    }


def ensure_foundation_roster_transition_authorization(
    db,
    previous_policy: dict,
    next_policy: dict,
    *,
    witness_url: str | None = None,
    timeout_seconds: float = 4.0,
    post_impl=None,
) -> dict:
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
                "operation": "external-roster-transition-authorize",
                "previousPolicy": previous_policy,
                "nextPolicy": next_policy,
            },
            timeout=timeout_seconds,
            follow_redirects=False,
        )
        data = _response_json(response)
    except FoundationWitnessError:
        raise
    except Exception as exc:
        raise FoundationWitnessError(
            "foundation-roster-transition-unavailable"
        ) from exc
    if int(response.status_code) >= 400:
        raise FoundationWitnessError(
            str(
                data.get("reasonCode")
                or "foundation-roster-transition-rejected"
            )
        )
    if (
        data.get("status") != "authorized"
        or data.get("authorizationVersion") != 1
        or data.get("authorizationType")
            != "decision_trace_trust_state_external_witness_roster_transition"
        or data.get("authAlgorithm") != "HMAC-SHA-256"
        or data.get("witnessId") != WITNESS_ID
        or data.get("fromGeneration") != previous_policy.get("generation")
        or data.get("toGeneration") != next_policy.get("generation")
        or data.get("fromPolicySha256")
            != previous_policy.get("policySha256")
        or data.get("toPolicySha256")
            != next_policy.get("policySha256")
        or not isinstance(data.get("authTag"), str)
        or SHA256_RE.fullmatch(data["authTag"]) is None
    ):
        raise FoundationWitnessError(
            "foundation-roster-transition-response-invalid"
        )
    return data


def _policy_transition_authorization_projection(
    value: Any,
    *,
    previous_policy: dict,
    next_policy: dict,
) -> dict:
    if not isinstance(value, dict) or value.get("status") != "authorized":
        raise FoundationWitnessError(
            str(
                value.get("reasonCode")
                if isinstance(value, dict)
                else "foundation-policy-transition-response-invalid"
            )
            or "foundation-policy-transition-response-invalid"
        )

    result = {
        "authorizationVersion": value.get("authorizationVersion"),
        "authorizationType": value.get("authorizationType"),
        "authAlgorithm": value.get("authAlgorithm"),
        "witnessId": value.get("witnessId"),
        "authKeyId": value.get("authKeyId"),
        "fromGeneration": value.get("fromGeneration"),
        "toGeneration": value.get("toGeneration"),
        "fromPolicySha256": value.get("fromPolicySha256"),
        "toPolicySha256": value.get("toPolicySha256"),
        "authTag": value.get("authTag"),
    }
    if (
        result["authorizationVersion"] != 1
        or result["authorizationType"]
        != "decision_trace_trust_state_witness_quorum_policy_transition"
        or result["authAlgorithm"] != "HMAC-SHA-256"
        or result["witnessId"] != WITNESS_ID
        or not isinstance(result["authKeyId"], str)
        or not result["authKeyId"]
        or result["fromGeneration"] != previous_policy.get("generation")
        or result["toGeneration"] != next_policy.get("generation")
        or result["fromPolicySha256"] != previous_policy.get("policySha256")
        or result["toPolicySha256"] != next_policy.get("policySha256")
        or not isinstance(result["authTag"], str)
        or SHA256_RE.fullmatch(result["authTag"]) is None
    ):
        raise FoundationWitnessError(
            "foundation-policy-transition-response-invalid"
        )
    return result


def ensure_foundation_policy_transition_authorization(
    db,
    previous_policy: dict,
    next_policy: dict,
    *,
    witness_url: str | None = None,
    timeout_seconds: float = 4.0,
    post_impl=None,
) -> dict:
    """Return one Foundation-verified previous-quorum transition approval."""
    token = _client_token(db)
    post = post_impl or httpx.post
    base = _witness_url(witness_url)

    def call(payload: dict) -> dict:
        try:
            response = post(
                base,
                headers={
                    "X-Shine-Client-Token": token,
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=timeout_seconds,
                follow_redirects=False,
            )
            data = _response_json(response)
        except FoundationWitnessError:
            raise
        except Exception as exc:
            raise FoundationWitnessError(
                "foundation-policy-transition-unavailable"
            ) from exc
        if int(response.status_code) >= 400:
            raise FoundationWitnessError(
                str(
                    data.get("reasonCode")
                    or "foundation-policy-transition-rejected"
                )
            )
        return data

    authorization_raw = call({
        "operation": "policy-transition-authorize",
        "previousPolicy": previous_policy,
        "nextPolicy": next_policy,
    })
    authorization = _policy_transition_authorization_projection(
        authorization_raw,
        previous_policy=previous_policy,
        next_policy=next_policy,
    )

    verification = call({
        "operation": "policy-transition-verify",
        "previousPolicy": previous_policy,
        "nextPolicy": next_policy,
        "authorization": authorization,
    })
    if (
        verification.get("status") != "verified"
        or verification.get("witnessId") != WITNESS_ID
        or verification.get("fromGeneration")
        != previous_policy.get("generation")
        or verification.get("toGeneration")
        != next_policy.get("generation")
        or verification.get("fromPolicySha256")
        != previous_policy.get("policySha256")
        or verification.get("toPolicySha256")
        != next_policy.get("policySha256")
    ):
        raise FoundationWitnessError(
            "foundation-policy-transition-verification-failed"
        )

    return {
        **authorization,
        "verification_status": "foundation-verified",
    }


def _witness_projection(value: Any) -> dict:
    if not isinstance(value, dict):
        raise FoundationWitnessError("foundation-witness-response-invalid")
    if value.get("status") != "witnessed":
        raise FoundationWitnessError(
            str(value.get("reasonCode") or "foundation-witness-response-invalid")
        )
    fields = {
        "witness_id": value.get("witnessId"),
        "sequence": value.get("sequence"),
        "head_sha256": value.get("headSha256"),
        "generation": value.get("generation"),
        "keyset_sha256": value.get("keyset_sha256"),
        "state_sha256": value.get("stateSha256"),
        "auth_key_id": value.get("authKeyId"),
        "chain_version": value.get("chainVersion"),
        "previous_chain_tag": value.get("previousChainTag"),
        "chain_tag": value.get("chainTag"),
        "history_status": "verified",
    }
    if (
        fields["witness_id"] != WITNESS_ID
        or not isinstance(fields["sequence"], int)
        or fields["sequence"] < 1
        or not isinstance(fields["generation"], int)
        or fields["generation"] < 1
        or any(
            not isinstance(fields[key], str)
            or len(fields[key]) != 64
            for key in (
                "head_sha256",
                "keyset_sha256",
                "state_sha256",
            )
        )
        or not isinstance(fields["auth_key_id"], str)
        or not fields["auth_key_id"]
        or fields["chain_version"] != CHAIN_VERSION
        or any(
            not isinstance(fields[key], str)
            or SHA256_RE.fullmatch(fields[key]) is None
            for key in ("previous_chain_tag", "chain_tag")
        )
        or (
            fields["sequence"] == 1
            and fields["previous_chain_tag"] != GENESIS_CHAIN_TAG
        )
    ):
        raise FoundationWitnessError("foundation-witness-response-invalid")
    return fields


def _matches_head(witness: dict, head: dict) -> bool:
    return (
        witness["sequence"] == head["sequence"]
        and witness["head_sha256"] == head["headSha256"]
        and witness["generation"] == head["generation"]
        and witness["keyset_sha256"] == head["keyset_sha256"]
        and witness["state_sha256"] == head["stateSha256"]
    )


def ensure_foundation_trust_witness(
    db,
    state: Any,
    *,
    redis_client=None,
    witness_url: str | None = None,
    timeout_seconds: float = 4.0,
    get_impl=None,
    post_impl=None,
) -> dict:
    try:
        local = prepare_monotonic_head(
            state,
            redis_client=redis_client,
        )
    except TrustStorageError as exc:
        raise FoundationWitnessError(str(exc)) from exc

    head = local.get("head")
    if not isinstance(head, dict):
        raise FoundationWitnessError("foundation-witness-local-head-invalid")

    current_raw = _current_witness(
        db,
        witness_url=witness_url,
        timeout_seconds=timeout_seconds,
        get_impl=get_impl,
    )
    current_status = str(current_raw.get("status") or "")

    if current_status == "empty":
        if head["sequence"] != 1:
            raise FoundationWitnessError(
                "foundation-witness-history-missing"
            )
        witnessed_raw = _record_witness(
            db,
            head,
            witness_url=witness_url,
            timeout_seconds=timeout_seconds,
            post_impl=post_impl,
        )
        witnessed = _witness_projection(witnessed_raw)
        if not _matches_head(witnessed, head):
            raise FoundationWitnessError(
                "foundation-witness-commit-mismatch"
            )
        if witnessed["previous_chain_tag"] != GENESIS_CHAIN_TAG:
            raise FoundationWitnessError(
                "foundation-witness-chain-genesis-mismatch"
            )
        return {
            "status": "verified",
            **witnessed,
            "mode": "created",
            "independent_retention": "foundation-supabase",
        }

    current = _witness_projection(current_raw)
    if _matches_head(current, head):
        return {
            "status": "verified",
            **current,
            "mode": "existing-witness",
            "independent_retention": "foundation-supabase",
        }

    if current["sequence"] > head["sequence"]:
        raise FoundationWitnessError("foundation-witness-ahead")
    if current["sequence"] == head["sequence"]:
        raise FoundationWitnessError("foundation-witness-fork")
    if head["sequence"] != current["sequence"] + 1:
        raise FoundationWitnessError("foundation-witness-sequence-gap")

    witnessed_raw = _record_witness(
        db,
        head,
        witness_url=witness_url,
        timeout_seconds=timeout_seconds,
        post_impl=post_impl,
    )
    witnessed = _witness_projection(witnessed_raw)
    if not _matches_head(witnessed, head):
        raise FoundationWitnessError(
            "foundation-witness-commit-mismatch"
        )
    if witnessed["previous_chain_tag"] != current["chain_tag"]:
        raise FoundationWitnessError(
            "foundation-witness-chain-continuity-mismatch"
        )
    return {
        "status": "verified",
        **witnessed,
        "mode": "advanced",
        "independent_retention": "foundation-supabase",
    }


__all__ = [
    "DEFAULT_FOUNDATION_WITNESS_URL",
    "FoundationWitnessError",
    "ROSTER_HEAD_WITNESS_ID",
    "ROSTER_HEAD_WITNESS_TYPE",
    "WITNESS_ID",
    "ensure_foundation_policy_transition_authorization",
    "ensure_foundation_roster_head_witness",
    "ensure_foundation_roster_transition_authorization",
    "ensure_foundation_trust_witness",
]
