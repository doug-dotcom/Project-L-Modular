"""Independent Foundation witness for Project L's monotonic trust head."""

from __future__ import annotations

import os
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
MAX_RESPONSE_BYTES = 32 * 1024


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


def _local_witness_projection(local: dict, head: dict) -> dict:
    if (
        not isinstance(local, dict)
        or local.get("status") != "ready"
        or not isinstance(head, dict)
    ):
        raise FoundationWitnessError(
            "foundation-witness-local-head-invalid"
        )
    return {
        "status": "verified",
        "witness_id": "project-l-redis",
        "sequence": head["sequence"],
        "head_sha256": head["headSha256"],
        "generation": head["generation"],
        "keyset_sha256": head["keyset_sha256"],
        "state_sha256": head["stateSha256"],
        "auth_key_id": head["authKeyId"],
        "mode": str(local.get("mode") or "unknown"),
        "independent_retention": "railway-redis-volume",
    }


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
    local_witness = _local_witness_projection(local, head)

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
        return {
            "status": "verified",
            **witnessed,
            "mode": "created",
            "independent_retention": "foundation-supabase",
            "local_witness": local_witness,
        }

    current = _witness_projection(current_raw)
    if _matches_head(current, head):
        return {
            "status": "verified",
            **current,
            "mode": "existing-witness",
            "independent_retention": "foundation-supabase",
            "local_witness": local_witness,
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
    return {
        "status": "verified",
        **witnessed,
        "mode": "advanced",
        "independent_retention": "foundation-supabase",
        "local_witness": local_witness,
    }


__all__ = [
    "DEFAULT_FOUNDATION_WITNESS_URL",
    "FoundationWitnessError",
    "WITNESS_ID",
    "ensure_foundation_trust_witness",
]
