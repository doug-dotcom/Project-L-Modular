"""Layer 208: append-only external-witness roster checkpoint chain.

The authenticated roster state is mutable high-water state. This module adds a
separate append-only history plus a monotonic head retained on Railway Redis.

Stable checkpoint/head SHA-256 identities intentionally exclude HMAC key IDs and
tags so local authentication-key rotation cannot rewrite trust history.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from typing import Any

from redis import Redis
from redis.exceptions import RedisError

SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
KEY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")

TRUST_STATE_TYPE = (
    "decision_trace_trust_state_witness_quorum_policy_"
    "external_head_witness_quorum_policy"
)
CHAIN_TYPE = (
    "decision_trace_trust_state_witness_quorum_policy_"
    "external_head_witness_quorum_checkpoint_chain"
)
HEAD_TYPE = (
    "decision_trace_trust_state_witness_quorum_policy_"
    "external_head_witness_quorum_monotonic_head"
)
CHAIN_AUTH_DOMAIN = (
    "shine-ai:decision-trace-trust-state-witness-quorum-policy-"
    "external-head-witness-quorum-checkpoint-chain:v1"
)
HEAD_AUTH_DOMAIN = (
    "shine-ai:decision-trace-trust-state-witness-quorum-policy-"
    "external-head-witness-quorum-monotonic-head:v1"
)
REDIS_HEAD_KEY = (
    "shine:project-l:trace-trust:external-witness-roster:head:v1"
)

_HEAD_CAS = r"""
local key = KEYS[1]
local sequence = tonumber(ARGV[1])
local checkpoint_sha = ARGV[2]
local generation = tonumber(ARGV[3])
local policy_sha = ARGV[4]
local state_sha = ARGV[5]
local previous_checkpoint_sha = ARGV[6]
local head_json = ARGV[7]

local current_sequence_raw = redis.call('HGET', key, 'sequence')
if not current_sequence_raw then
  if sequence ~= 1 or previous_checkpoint_sha ~= '' then
    return {'genesis-invalid'}
  end
  redis.call(
    'HSET', key,
    'sequence', tostring(sequence),
    'checkpoint_sha256', checkpoint_sha,
    'generation', tostring(generation),
    'policy_sha256', policy_sha,
    'state_sha256', state_sha,
    'head_json', head_json
  )
  return {'created'}
end

local current_sequence = tonumber(current_sequence_raw)
local current_checkpoint = redis.call('HGET', key, 'checkpoint_sha256') or ''
local current_generation = tonumber(redis.call('HGET', key, 'generation') or '0')
local current_policy = redis.call('HGET', key, 'policy_sha256') or ''
local current_state = redis.call('HGET', key, 'state_sha256') or ''

if sequence < current_sequence then return {'rollback'} end
if sequence > current_sequence + 1 then return {'sequence-skip'} end

if sequence == current_sequence then
  if checkpoint_sha ~= current_checkpoint
     or generation ~= current_generation
     or policy_sha ~= current_policy
     or state_sha ~= current_state then
    return {'fork'}
  end
  redis.call('HSET', key, 'head_json', head_json)
  return {'refreshed'}
end

if previous_checkpoint_sha ~= current_checkpoint then
  return {'predecessor-checkpoint-mismatch'}
end
if generation ~= current_generation + 1 then
  return {'generation-mismatch'}
end

redis.call(
  'HSET', key,
  'sequence', tostring(sequence),
  'checkpoint_sha256', checkpoint_sha,
  'generation', tostring(generation),
  'policy_sha256', policy_sha,
  'state_sha256', state_sha,
  'head_json', head_json
)
return {'advanced'}
"""


class ExternalWitnessRosterChainError(RuntimeError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hmac_sha256(secret: str, value: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _keyring() -> tuple[str, dict[str, str]]:
    raw = os.getenv(
        "SHINE_TRACE_EXTERNAL_WITNESS_ROSTER_CHAIN_KEYRING_JSON",
        "",
    ).strip()
    active = os.getenv(
        "SHINE_TRACE_EXTERNAL_WITNESS_ROSTER_CHAIN_ACTIVE_KEY_ID",
        "",
    ).strip()
    try:
        parsed = json.loads(raw)
    except Exception as exc:
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-chain-keyring-invalid"
        ) from exc
    if (
        not isinstance(parsed, dict)
        or not 1 <= len(parsed) <= 4
        or KEY_ID_RE.fullmatch(active) is None
    ):
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-chain-keyring-invalid"
        )
    keyring: dict[str, str] = {}
    for raw_key, secret in parsed.items():
        key_id = str(raw_key)
        if (
            KEY_ID_RE.fullmatch(key_id) is None
            or not isinstance(secret, str)
            or len(secret) < 32
            or len(secret) > 8192
        ):
            raise ExternalWitnessRosterChainError(
                "external-witness-roster-chain-keyring-invalid"
            )
        keyring[key_id] = secret
    if active not in keyring:
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-chain-active-key-unavailable"
        )
    return active, keyring


def _secret(key_id: str) -> str:
    _active, keyring = _keyring()
    value = keyring.get(key_id)
    if value is None:
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-chain-key-retired"
        )
    return value


def _redis_client(redis_client=None):
    if redis_client is not None:
        return redis_client
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-head-redis-unavailable"
        )
    return Redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=3,
        socket_timeout=3,
        health_check_interval=30,
    )


def project_state(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-chain-state-invalid"
        )
    generation = value.get("generation")
    minimum = value.get("minimumWitnesses")
    ids = value.get("acceptedWitnessIds")
    previous = value.get("previousPolicySha256")
    policy_sha = value.get("policySha256")
    if (
        value.get("trustStateVersion") != 1
        or value.get("trustStateType") != TRUST_STATE_TYPE
        or not isinstance(generation, int)
        or isinstance(generation, bool)
        or not 1 <= generation <= 1_000_000
        or not isinstance(minimum, int)
        or isinstance(minimum, bool)
        or not isinstance(ids, list)
        or not 2 <= len(ids) <= 4
        or ids != sorted(ids)
        or len(ids) != len(set(ids))
        or minimum < 2
        or minimum > len(ids)
        or any(
            not isinstance(item, str)
            or KEY_ID_RE.fullmatch(item) is None
            for item in ids
        )
        or not isinstance(policy_sha, str)
        or SHA256_RE.fullmatch(policy_sha) is None
    ):
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-chain-state-invalid"
        )
    if generation == 1:
        if previous is not None:
            raise ExternalWitnessRosterChainError(
                "external-witness-roster-chain-state-invalid"
            )
    elif (
        not isinstance(previous, str)
        or SHA256_RE.fullmatch(previous) is None
    ):
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-chain-state-invalid"
        )
    return {
        "trustStateVersion": 1,
        "trustStateType": TRUST_STATE_TYPE,
        "generation": generation,
        "minimumWitnesses": minimum,
        "acceptedWitnessIds": list(ids),
        "previousPolicySha256": previous,
        "policySha256": policy_sha,
    }


def digest_state(state: Any) -> str:
    return _sha256_text(_canonical_json(project_state(state)))


def _checkpoint_material(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "chainVersion": 1,
        "chainType": CHAIN_TYPE,
        "sequence": value["sequence"],
        "previousCheckpointSha256": value["previousCheckpointSha256"],
        "trustStateVersion": 1,
        "generation": value["generation"],
        "previousPolicySha256": value["previousPolicySha256"],
        "policySha256": value["policySha256"],
        "stateSha256": value["stateSha256"],
    }


def create_checkpoint(
    state: Any,
    *,
    previous_checkpoint: dict[str, Any] | None = None,
    auth_key_id: str | None = None,
) -> dict[str, Any]:
    projected = project_state(state)
    active, keyring = _keyring()
    key_id = auth_key_id or active
    if key_id not in keyring:
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-chain-auth-key-unavailable"
        )
    state_sha = digest_state(projected)
    if previous_checkpoint is None:
        if (
            projected["generation"] != 1
            or projected["previousPolicySha256"] is not None
        ):
            raise ExternalWitnessRosterChainError(
                "external-witness-roster-chain-genesis-invalid"
            )
        sequence = 1
        previous_checkpoint_sha = None
    else:
        previous = verify_checkpoint(previous_checkpoint)
        if (
            projected["generation"] != previous["generation"] + 1
            or projected["previousPolicySha256"]
            != previous["policySha256"]
        ):
            raise ExternalWitnessRosterChainError(
                "external-witness-roster-chain-continuity-invalid"
            )
        sequence = previous["sequence"] + 1
        previous_checkpoint_sha = previous["checkpointSha256"]

    base = {
        "chainVersion": 1,
        "chainType": CHAIN_TYPE,
        "authAlgorithm": "HMAC-SHA-256",
        "authKeyId": key_id,
        "sequence": sequence,
        "previousCheckpointSha256": previous_checkpoint_sha,
        "trustStateVersion": 1,
        "generation": projected["generation"],
        "previousPolicySha256": projected["previousPolicySha256"],
        "policySha256": projected["policySha256"],
        "stateSha256": state_sha,
    }
    material = _canonical_json(_checkpoint_material(base))
    checkpoint_sha = _sha256_text(material)
    return {
        **base,
        "checkpointSha256": checkpoint_sha,
        "authTag": _hmac_sha256(
            keyring[key_id],
            CHAIN_AUTH_DOMAIN
            + "\n"
            + key_id
            + "\n"
            + checkpoint_sha
            + "\n"
            + material,
        ),
    }


def verify_checkpoint(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-chain-checkpoint-invalid"
        )
    key_id = value.get("authKeyId")
    sequence = value.get("sequence")
    previous_checkpoint = value.get("previousCheckpointSha256")
    generation = value.get("generation")
    previous_policy = value.get("previousPolicySha256")
    policy_sha = value.get("policySha256")
    state_sha = value.get("stateSha256")
    checkpoint_sha = value.get("checkpointSha256")
    auth_tag = value.get("authTag")
    if (
        value.get("chainVersion") != 1
        or value.get("chainType") != CHAIN_TYPE
        or value.get("authAlgorithm") != "HMAC-SHA-256"
        or not isinstance(key_id, str)
        or KEY_ID_RE.fullmatch(key_id) is None
        or not isinstance(sequence, int)
        or isinstance(sequence, bool)
        or not 1 <= sequence <= 1_000_000
        or value.get("trustStateVersion") != 1
        or not isinstance(generation, int)
        or isinstance(generation, bool)
        or not 1 <= generation <= 1_000_000
        or not isinstance(policy_sha, str)
        or SHA256_RE.fullmatch(policy_sha) is None
        or not isinstance(state_sha, str)
        or SHA256_RE.fullmatch(state_sha) is None
        or not isinstance(checkpoint_sha, str)
        or SHA256_RE.fullmatch(checkpoint_sha) is None
        or not isinstance(auth_tag, str)
        or SHA256_RE.fullmatch(auth_tag) is None
    ):
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-chain-checkpoint-invalid"
        )
    if sequence == 1:
        if (
            previous_checkpoint is not None
            or generation != 1
            or previous_policy is not None
        ):
            raise ExternalWitnessRosterChainError(
                "external-witness-roster-chain-checkpoint-invalid"
            )
    elif (
        not isinstance(previous_checkpoint, str)
        or SHA256_RE.fullmatch(previous_checkpoint) is None
        or not isinstance(previous_policy, str)
        or SHA256_RE.fullmatch(previous_policy) is None
    ):
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-chain-checkpoint-invalid"
        )
    projected = {
        "chainVersion": 1,
        "chainType": CHAIN_TYPE,
        "authAlgorithm": "HMAC-SHA-256",
        "authKeyId": key_id,
        "sequence": sequence,
        "previousCheckpointSha256": previous_checkpoint,
        "trustStateVersion": 1,
        "generation": generation,
        "previousPolicySha256": previous_policy,
        "policySha256": policy_sha,
        "stateSha256": state_sha,
        "checkpointSha256": checkpoint_sha,
        "authTag": auth_tag,
    }
    material = _canonical_json(_checkpoint_material(projected))
    if _sha256_text(material) != checkpoint_sha:
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-chain-checkpoint-digest-mismatch"
        )
    expected = _hmac_sha256(
        _secret(key_id),
        CHAIN_AUTH_DOMAIN
        + "\n"
        + key_id
        + "\n"
        + checkpoint_sha
        + "\n"
        + material,
    )
    if not hmac.compare_digest(expected, auth_tag):
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-chain-checkpoint-auth-failed"
        )
    return projected


def _head_material(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "headVersion": 1,
        "headType": HEAD_TYPE,
        "checkpointChainVersion": 1,
        "sequence": value["sequence"],
        "checkpointSha256": value["checkpointSha256"],
        "generation": value["generation"],
        "policySha256": value["policySha256"],
        "stateSha256": value["stateSha256"],
    }


def create_head(
    checkpoint: Any,
    *,
    auth_key_id: str | None = None,
) -> dict[str, Any]:
    cp = verify_checkpoint(checkpoint)
    active, keyring = _keyring()
    key_id = auth_key_id or active
    if key_id not in keyring:
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-head-auth-key-unavailable"
        )
    base = {
        "headVersion": 1,
        "headType": HEAD_TYPE,
        "authAlgorithm": "HMAC-SHA-256",
        "authKeyId": key_id,
        "checkpointChainVersion": 1,
        "sequence": cp["sequence"],
        "checkpointSha256": cp["checkpointSha256"],
        "generation": cp["generation"],
        "policySha256": cp["policySha256"],
        "stateSha256": cp["stateSha256"],
    }
    material = _canonical_json(_head_material(base))
    head_sha = _sha256_text(material)
    return {
        **base,
        "headSha256": head_sha,
        "authTag": _hmac_sha256(
            keyring[key_id],
            HEAD_AUTH_DOMAIN
            + "\n"
            + key_id
            + "\n"
            + head_sha
            + "\n"
            + material,
        ),
    }


def verify_head(
    value: Any,
    *,
    expected_head_sha256: str | None = None,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-head-invalid"
        )
    key_id = value.get("authKeyId")
    sequence = value.get("sequence")
    checkpoint_sha = value.get("checkpointSha256")
    generation = value.get("generation")
    policy_sha = value.get("policySha256")
    state_sha = value.get("stateSha256")
    head_sha = value.get("headSha256")
    auth_tag = value.get("authTag")
    if (
        value.get("headVersion") != 1
        or value.get("headType") != HEAD_TYPE
        or value.get("authAlgorithm") != "HMAC-SHA-256"
        or not isinstance(key_id, str)
        or KEY_ID_RE.fullmatch(key_id) is None
        or value.get("checkpointChainVersion") != 1
        or not isinstance(sequence, int)
        or isinstance(sequence, bool)
        or not 1 <= sequence <= 1_000_000
        or any(
            not isinstance(item, str)
            or SHA256_RE.fullmatch(item) is None
            for item in (
                checkpoint_sha,
                policy_sha,
                state_sha,
                head_sha,
                auth_tag,
            )
        )
        or not isinstance(generation, int)
        or isinstance(generation, bool)
        or not 1 <= generation <= 1_000_000
    ):
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-head-invalid"
        )
    if (
        expected_head_sha256 is not None
        and expected_head_sha256 != head_sha
    ):
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-head-pin-mismatch"
        )
    projected = {
        "headVersion": 1,
        "headType": HEAD_TYPE,
        "authAlgorithm": "HMAC-SHA-256",
        "authKeyId": key_id,
        "checkpointChainVersion": 1,
        "sequence": sequence,
        "checkpointSha256": checkpoint_sha,
        "generation": generation,
        "policySha256": policy_sha,
        "stateSha256": state_sha,
        "headSha256": head_sha,
        "authTag": auth_tag,
    }
    material = _canonical_json(_head_material(projected))
    if _sha256_text(material) != head_sha:
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-head-digest-mismatch"
        )
    expected = _hmac_sha256(
        _secret(key_id),
        HEAD_AUTH_DOMAIN
        + "\n"
        + key_id
        + "\n"
        + head_sha
        + "\n"
        + material,
    )
    if not hmac.compare_digest(expected, auth_tag):
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-head-auth-failed"
        )
    return projected


def read_head(*, redis_client=None) -> dict[str, Any] | None:
    client = _redis_client(redis_client)
    try:
        data = client.hgetall(REDIS_HEAD_KEY)
    except RedisError as exc:
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-head-redis-unavailable"
        ) from exc
    if not data:
        return None
    raw = data.get("head_json")
    if not isinstance(raw, str) or not raw:
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-head-storage-invalid"
        )
    try:
        head = verify_head(json.loads(raw))
    except ExternalWitnessRosterChainError:
        raise
    except Exception as exc:
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-head-storage-invalid"
        ) from exc
    if (
        str(data.get("sequence") or "") != str(head["sequence"])
        or data.get("checkpoint_sha256") != head["checkpointSha256"]
        or str(data.get("generation") or "") != str(head["generation"])
        or data.get("policy_sha256") != head["policySha256"]
        or data.get("state_sha256") != head["stateSha256"]
    ):
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-head-storage-mismatch"
        )
    return head


def persist_head(
    checkpoint: Any,
    *,
    auth_key_id: str | None = None,
    redis_client=None,
) -> dict[str, Any]:
    cp = verify_checkpoint(checkpoint)
    head = create_head(cp, auth_key_id=auth_key_id)
    client = _redis_client(redis_client)
    try:
        result = client.eval(
            _HEAD_CAS,
            1,
            REDIS_HEAD_KEY,
            str(head["sequence"]),
            head["checkpointSha256"],
            str(head["generation"]),
            head["policySha256"],
            head["stateSha256"],
            cp["previousCheckpointSha256"] or "",
            _canonical_json(head),
        )
    except RedisError as exc:
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-head-redis-unavailable"
        ) from exc
    code = (
        str(result[0])
        if isinstance(result, (list, tuple)) and result
        else str(result or "")
    )
    if code not in {"created", "refreshed", "advanced"}:
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-head-cas-" + (code or "failed")
        )
    stored = read_head(redis_client=client)
    if (
        stored is None
        or stored["headSha256"] != head["headSha256"]
        or stored["checkpointSha256"] != head["checkpointSha256"]
    ):
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-head-write-unverified"
        )
    return {
        "status": "verified",
        "mode": code,
        "sequence": head["sequence"],
        "checkpoint_sha256": head["checkpointSha256"],
        "generation": head["generation"],
        "policy_sha256": head["policySha256"],
        "state_sha256": head["stateSha256"],
        "head_sha256": head["headSha256"],
        "auth_key_id": head["authKeyId"],
        "independent_retention": "railway-redis-volume",
    }


def _chain_snapshot(db) -> list[dict[str, Any]]:
    try:
        result = db.rpc(
            "shine_ai_external_witness_roster_chain_snapshot_v1",
            {},
        ).execute()
    except Exception as exc:
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-chain-snapshot-unavailable"
        ) from exc
    payload = result.data if isinstance(result.data, dict) else {}
    if payload.get("status") not in {"empty", "ok"}:
        raise ExternalWitnessRosterChainError(
            str(
                payload.get("reason_code")
                or "external-witness-roster-chain-storage-invalid"
            )
        )
    records = payload.get("records")
    if payload.get("status") == "empty":
        return []
    if not isinstance(records, list) or len(records) > 1_000_000:
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-chain-storage-invalid"
        )
    return records


def verify_chain(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    verified: list[dict[str, Any]] = []
    for raw in records:
        current = verify_checkpoint(raw)
        if not verified:
            if (
                current["sequence"] != 1
                or current["generation"] != 1
                or current["previousCheckpointSha256"] is not None
                or current["previousPolicySha256"] is not None
            ):
                raise ExternalWitnessRosterChainError(
                    "external-witness-roster-chain-genesis-invalid"
                )
        else:
            previous = verified[-1]
            if (
                current["sequence"] != previous["sequence"] + 1
                or current["generation"] != previous["generation"] + 1
                or current["previousCheckpointSha256"]
                != previous["checkpointSha256"]
                or current["previousPolicySha256"]
                != previous["policySha256"]
            ):
                raise ExternalWitnessRosterChainError(
                    "external-witness-roster-chain-continuity-invalid"
                )
        verified.append(current)
    return verified


def _append_chain_record(db, record: dict[str, Any]) -> None:
    try:
        result = db.rpc(
            "shine_ai_external_witness_roster_chain_append_v1",
            {
                "p_sequence": record["sequence"],
                "p_previous_checkpoint_sha256":
                    record["previousCheckpointSha256"],
                "p_generation": record["generation"],
                "p_previous_policy_sha256":
                    record["previousPolicySha256"],
                "p_policy_sha256": record["policySha256"],
                "p_state_sha256": record["stateSha256"],
                "p_checkpoint_sha256": record["checkpointSha256"],
                "p_auth_key_id": record["authKeyId"],
                "p_auth_tag": record["authTag"],
            },
        ).execute()
    except Exception as exc:
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-chain-append-failed"
        ) from exc
    payload = result.data if isinstance(result.data, dict) else {}
    if payload.get("status") not in {"appended", "already_present"}:
        raise ExternalWitnessRosterChainError(
            str(
                payload.get("reason_code")
                or "external-witness-roster-chain-append-unverified"
            )
        )


def ensure_roster_chain(
    db,
    state: Any,
    *,
    redis_client=None,
) -> dict[str, Any]:
    projected = project_state(state)
    records = verify_chain(_chain_snapshot(db))

    if not records:
        if projected["generation"] != 1:
            raise ExternalWitnessRosterChainError(
                "external-witness-roster-chain-history-missing"
            )
        checkpoint = create_checkpoint(projected)
        _append_chain_record(db, checkpoint)
        records = verify_chain(_chain_snapshot(db))
    else:
        latest = records[-1]
        if latest["generation"] > projected["generation"]:
            raise ExternalWitnessRosterChainError(
                "external-witness-roster-chain-ahead"
            )
        if latest["generation"] == projected["generation"]:
            if (
                latest["policySha256"] != projected["policySha256"]
                or latest["stateSha256"] != digest_state(projected)
            ):
                raise ExternalWitnessRosterChainError(
                    "external-witness-roster-chain-state-mismatch"
                )
        elif latest["generation"] + 1 == projected["generation"]:
            checkpoint = create_checkpoint(
                projected,
                previous_checkpoint=latest,
            )
            _append_chain_record(db, checkpoint)
            records = verify_chain(_chain_snapshot(db))
        else:
            raise ExternalWitnessRosterChainError(
                "external-witness-roster-chain-generation-gap"
            )

    latest = records[-1]
    if (
        latest["generation"] != projected["generation"]
        or latest["policySha256"] != projected["policySha256"]
        or latest["stateSha256"] != digest_state(projected)
    ):
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-chain-high-water-mismatch"
        )

    head_receipt = persist_head(
        latest,
        redis_client=redis_client,
    )
    head = read_head(redis_client=redis_client)
    if (
        head is None
        or head["sequence"] != latest["sequence"]
        or head["checkpointSha256"] != latest["checkpointSha256"]
        or head["generation"] != latest["generation"]
        or head["policySha256"] != latest["policySha256"]
        or head["stateSha256"] != latest["stateSha256"]
    ):
        raise ExternalWitnessRosterChainError(
            "external-witness-roster-head-chain-mismatch"
        )

    return {
        "status": "verified",
        "chain_version": 1,
        "sequence": latest["sequence"],
        "generation": latest["generation"],
        "previous_checkpoint_sha256":
            latest["previousCheckpointSha256"],
        "checkpoint_sha256": latest["checkpointSha256"],
        "policy_sha256": latest["policySha256"],
        "state_sha256": latest["stateSha256"],
        "head_version": 1,
        "head_sha256": head["headSha256"],
        "head_auth_key_id": head["authKeyId"],
        "head_mode": head_receipt["mode"],
        "head_independent_retention": "railway-redis-volume",
        "history_records_verified": len(records),
    }


__all__ = [
    "CHAIN_AUTH_DOMAIN",
    "CHAIN_TYPE",
    "ExternalWitnessRosterChainError",
    "HEAD_AUTH_DOMAIN",
    "HEAD_TYPE",
    "REDIS_HEAD_KEY",
    "create_checkpoint",
    "create_head",
    "digest_state",
    "ensure_roster_chain",
    "persist_head",
    "project_state",
    "read_head",
    "verify_chain",
    "verify_checkpoint",
    "verify_head",
]
