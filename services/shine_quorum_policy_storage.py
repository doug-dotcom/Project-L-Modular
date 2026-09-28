"""Authenticated persistence for Project L witness-quorum policy trust.

The policy itself stays unchanged. This module only authenticates its persisted
trust-state envelope and an independently retained Redis rollback checkpoint,
and supports overlap-safe HMAC storage-key rotation.
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

POLICY_TYPE = "decision_trace_trust_state_witness_quorum_policy"
STATE_AUTH_DOMAIN = (
    "shine-ai:decision-trace-trust-state-witness-quorum-policy-state:v1"
)
CHECKPOINT_AUTH_DOMAIN = (
    "shine-ai:decision-trace-trust-state-witness-quorum-policy-state-checkpoint:v1"
)
REDIS_POLICY_CHECKPOINT_KEY = (
    "shine:project-l:trace-trust:witness-quorum-policy:checkpoint:v1"
)

_ENVELOPE_TYPE = (
    "decision_trace_trust_state_witness_quorum_policy_authenticated"
)
_CHECKPOINT_TYPE = (
    "decision_trace_trust_state_witness_quorum_policy_rollback_checkpoint"
)

_CHECKPOINT_CAS = r"""
local key = KEYS[1]
local generation = tonumber(ARGV[1])
local policy_sha = ARGV[2]
local state_sha = ARGV[3]
local previous_policy_sha = ARGV[4]
local checkpoint_json = ARGV[5]

local current_generation = redis.call('HGET', key, 'generation')
if not current_generation then
  if generation ~= 1 then return {'bootstrap-generation-invalid'} end
  if previous_policy_sha ~= '' then return {'bootstrap-predecessor-invalid'} end
  redis.call(
    'HSET', key,
    'generation', tostring(generation),
    'policy_sha256', policy_sha,
    'state_sha256', state_sha,
    'checkpoint_json', checkpoint_json
  )
  return {'created'}
end

current_generation = tonumber(current_generation)
local current_policy_sha = redis.call('HGET', key, 'policy_sha256') or ''
local current_state_sha = redis.call('HGET', key, 'state_sha256') or ''

if generation < current_generation then return {'rollback'} end
if generation > current_generation + 1 then return {'generation-skip'} end

if generation == current_generation then
  if policy_sha ~= current_policy_sha then return {'equivocation'} end
  if state_sha ~= current_state_sha then return {'state-mismatch'} end
  redis.call('HSET', key, 'checkpoint_json', checkpoint_json)
  return {'refreshed'}
end

if previous_policy_sha ~= current_policy_sha then
  return {'predecessor-policy-mismatch'}
end
if policy_sha == current_policy_sha then
  return {'generation-without-policy-change'}
end

redis.call(
  'HSET', key,
  'generation', tostring(generation),
  'policy_sha256', policy_sha,
  'state_sha256', state_sha,
  'checkpoint_json', checkpoint_json
)
return {'advanced'}
"""


class QuorumPolicyStorageError(RuntimeError):
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
        "SHINE_TRACE_WITNESS_QUORUM_POLICY_STORAGE_KEYRING_JSON",
        "",
    ).strip()
    active = os.getenv(
        "SHINE_TRACE_WITNESS_QUORUM_POLICY_STORAGE_ACTIVE_KEY_ID",
        "",
    ).strip()
    if not raw or KEY_ID_RE.fullmatch(active) is None:
        raise QuorumPolicyStorageError(
            "trust-witness-quorum-policy-storage-keyring-unavailable"
        )
    try:
        parsed = json.loads(raw)
    except Exception as exc:
        raise QuorumPolicyStorageError(
            "trust-witness-quorum-policy-storage-keyring-invalid"
        ) from exc
    if not isinstance(parsed, dict) or not 1 <= len(parsed) <= 4:
        raise QuorumPolicyStorageError(
            "trust-witness-quorum-policy-storage-keyring-invalid"
        )
    keyring: dict[str, str] = {}
    for raw_key, raw_secret in parsed.items():
        key_id = str(raw_key)
        if (
            KEY_ID_RE.fullmatch(key_id) is None
            or not isinstance(raw_secret, str)
            or len(raw_secret) < 32
            or len(raw_secret) > 8192
        ):
            raise QuorumPolicyStorageError(
                "trust-witness-quorum-policy-storage-keyring-invalid"
            )
        keyring[key_id] = raw_secret
    if active not in keyring:
        raise QuorumPolicyStorageError(
            "trust-witness-quorum-policy-storage-active-key-unavailable"
        )
    return active, keyring


def _secret(key_id: str) -> str:
    _active, keyring = _keyring()
    value = keyring.get(key_id)
    if value is None:
        raise QuorumPolicyStorageError(
            "trust-witness-quorum-policy-storage-key-retired"
        )
    return value


def project_policy_state(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise QuorumPolicyStorageError(
            "trust-witness-quorum-policy-storage-state-invalid"
        )
    ids = value.get("acceptedWitnessIds")
    generation = value.get("generation")
    minimum = value.get("minimumWitnesses")
    previous = value.get("previousPolicySha256")
    policy_sha = value.get("policySha256")
    if (
        value.get("trustStateVersion") != 1
        or value.get("trustStateType") != POLICY_TYPE
        or not isinstance(generation, int)
        or isinstance(generation, bool)
        or not 1 <= generation <= 1_000_000
        or not isinstance(minimum, int)
        or isinstance(minimum, bool)
        or not isinstance(ids, list)
        or not 2 <= len(ids) <= 4
        or ids != sorted(ids)
        or len(set(ids)) != len(ids)
        or any(
            not isinstance(item, str)
            or KEY_ID_RE.fullmatch(item) is None
            for item in ids
        )
        or minimum < 2
        or minimum > len(ids)
        or not isinstance(policy_sha, str)
        or SHA256_RE.fullmatch(policy_sha) is None
    ):
        raise QuorumPolicyStorageError(
            "trust-witness-quorum-policy-storage-state-invalid"
        )
    if generation == 1:
        if previous is not None:
            raise QuorumPolicyStorageError(
                "trust-witness-quorum-policy-storage-state-invalid"
            )
    elif not isinstance(previous, str) or SHA256_RE.fullmatch(previous) is None:
        raise QuorumPolicyStorageError(
            "trust-witness-quorum-policy-storage-state-invalid"
        )

    material = {
        "policyVersion": 1,
        "policyType": POLICY_TYPE,
        "generation": generation,
        "minimumWitnesses": minimum,
        "acceptedWitnessIds": list(ids),
        "previousPolicySha256": previous,
    }
    if _sha256_text(_canonical_json(material)) != policy_sha:
        raise QuorumPolicyStorageError(
            "trust-witness-quorum-policy-storage-policy-digest-mismatch"
        )

    return {
        "trustStateVersion": 1,
        "trustStateType": POLICY_TYPE,
        "generation": generation,
        "minimumWitnesses": minimum,
        "acceptedWitnessIds": list(ids),
        "previousPolicySha256": previous,
        "policySha256": policy_sha,
    }


def serialize_policy_state(state: Any) -> str:
    return _canonical_json(project_policy_state(state))


def digest_policy_state(state: Any) -> str:
    return _sha256_text(serialize_policy_state(state))


def create_envelope(
    state: Any,
    *,
    auth_key_id: str | None = None,
) -> dict[str, Any]:
    projected = project_policy_state(state)
    active, keyring = _keyring()
    key_id = auth_key_id or active
    if KEY_ID_RE.fullmatch(key_id) is None or key_id not in keyring:
        raise QuorumPolicyStorageError(
            "trust-witness-quorum-policy-storage-auth-key-unavailable"
        )
    serialized = serialize_policy_state(projected)
    state_sha = _sha256_text(serialized)
    material = (
        STATE_AUTH_DOMAIN
        + "\n"
        + key_id
        + "\n"
        + state_sha
        + "\n"
        + serialized
    )
    return {
        "envelopeVersion": 1,
        "envelopeType": _ENVELOPE_TYPE,
        "authAlgorithm": "HMAC-SHA-256",
        "authKeyId": key_id,
        "stateSha256": state_sha,
        "authTag": _hmac_sha256(keyring[key_id], material),
        "state": projected,
    }


def verify_envelope(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise QuorumPolicyStorageError(
            "trust-witness-quorum-policy-storage-envelope-invalid"
        )
    key_id = value.get("authKeyId")
    state_sha = value.get("stateSha256")
    auth_tag = value.get("authTag")
    if (
        value.get("envelopeVersion") != 1
        or value.get("envelopeType") != _ENVELOPE_TYPE
        or value.get("authAlgorithm") != "HMAC-SHA-256"
        or not isinstance(key_id, str)
        or KEY_ID_RE.fullmatch(key_id) is None
        or not isinstance(state_sha, str)
        or SHA256_RE.fullmatch(state_sha) is None
        or not isinstance(auth_tag, str)
        or SHA256_RE.fullmatch(auth_tag) is None
    ):
        raise QuorumPolicyStorageError(
            "trust-witness-quorum-policy-storage-envelope-invalid"
        )
    state = project_policy_state(value.get("state"))
    serialized = serialize_policy_state(state)
    actual_sha = _sha256_text(serialized)
    if not hmac.compare_digest(actual_sha, state_sha):
        raise QuorumPolicyStorageError(
            "trust-witness-quorum-policy-storage-envelope-digest-mismatch"
        )
    material = (
        STATE_AUTH_DOMAIN
        + "\n"
        + key_id
        + "\n"
        + state_sha
        + "\n"
        + serialized
    )
    if not hmac.compare_digest(
        _hmac_sha256(_secret(key_id), material),
        auth_tag,
    ):
        raise QuorumPolicyStorageError(
            "trust-witness-quorum-policy-storage-envelope-auth-failed"
        )
    return state


def create_checkpoint(
    state: Any,
    *,
    auth_key_id: str | None = None,
) -> dict[str, Any]:
    projected = project_policy_state(state)
    active, keyring = _keyring()
    key_id = auth_key_id or active
    if KEY_ID_RE.fullmatch(key_id) is None or key_id not in keyring:
        raise QuorumPolicyStorageError(
            "trust-witness-quorum-policy-storage-auth-key-unavailable"
        )
    state_sha = digest_policy_state(projected)
    base = {
        "checkpointVersion": 1,
        "checkpointType": _CHECKPOINT_TYPE,
        "authAlgorithm": "HMAC-SHA-256",
        "authKeyId": key_id,
        "trustStateVersion": 1,
        "generation": projected["generation"],
        "policySha256": projected["policySha256"],
        "stateSha256": state_sha,
    }
    material = _canonical_json({
        "checkpointVersion": 1,
        "checkpointType": _CHECKPOINT_TYPE,
        "trustStateVersion": 1,
        "generation": projected["generation"],
        "policySha256": projected["policySha256"],
        "stateSha256": state_sha,
    })
    return {
        **base,
        "authTag": _hmac_sha256(
            keyring[key_id],
            CHECKPOINT_AUTH_DOMAIN
            + "\n"
            + key_id
            + "\n"
            + material,
        ),
    }


def verify_checkpoint(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise QuorumPolicyStorageError(
            "trust-witness-quorum-policy-storage-checkpoint-invalid"
        )
    key_id = value.get("authKeyId")
    generation = value.get("generation")
    policy_sha = value.get("policySha256")
    state_sha = value.get("stateSha256")
    auth_tag = value.get("authTag")
    if (
        value.get("checkpointVersion") != 1
        or value.get("checkpointType") != _CHECKPOINT_TYPE
        or value.get("authAlgorithm") != "HMAC-SHA-256"
        or value.get("trustStateVersion") != 1
        or not isinstance(key_id, str)
        or KEY_ID_RE.fullmatch(key_id) is None
        or not isinstance(generation, int)
        or isinstance(generation, bool)
        or not 1 <= generation <= 1_000_000
        or not isinstance(policy_sha, str)
        or SHA256_RE.fullmatch(policy_sha) is None
        or not isinstance(state_sha, str)
        or SHA256_RE.fullmatch(state_sha) is None
        or not isinstance(auth_tag, str)
        or SHA256_RE.fullmatch(auth_tag) is None
    ):
        raise QuorumPolicyStorageError(
            "trust-witness-quorum-policy-storage-checkpoint-invalid"
        )
    material = _canonical_json({
        "checkpointVersion": 1,
        "checkpointType": _CHECKPOINT_TYPE,
        "trustStateVersion": 1,
        "generation": generation,
        "policySha256": policy_sha,
        "stateSha256": state_sha,
    })
    if not hmac.compare_digest(
        _hmac_sha256(
            _secret(key_id),
            CHECKPOINT_AUTH_DOMAIN
            + "\n"
            + key_id
            + "\n"
            + material,
        ),
        auth_tag,
    ):
        raise QuorumPolicyStorageError(
            "trust-witness-quorum-policy-storage-checkpoint-auth-failed"
        )
    return {
        "checkpointVersion": 1,
        "checkpointType": _CHECKPOINT_TYPE,
        "authAlgorithm": "HMAC-SHA-256",
        "authKeyId": key_id,
        "trustStateVersion": 1,
        "generation": generation,
        "policySha256": policy_sha,
        "stateSha256": state_sha,
        "authTag": auth_tag,
    }


def verify_pair(
    envelope: Any,
    checkpoint: Any,
) -> dict[str, Any]:
    state = verify_envelope(envelope)
    cp = verify_checkpoint(checkpoint)
    if (
        state["generation"] != cp["generation"]
        or state["policySha256"] != cp["policySha256"]
        or digest_policy_state(state) != cp["stateSha256"]
        or envelope.get("stateSha256") != cp["stateSha256"]
    ):
        raise QuorumPolicyStorageError(
            "trust-witness-quorum-policy-storage-pair-mismatch"
        )
    return state


def rotate_pair(
    envelope: Any,
    checkpoint: Any,
    target_auth_key_id: str,
) -> dict[str, Any]:
    state = verify_pair(envelope, checkpoint)
    active, keyring = _keyring()
    _ = active
    if (
        KEY_ID_RE.fullmatch(target_auth_key_id) is None
        or target_auth_key_id not in keyring
    ):
        raise QuorumPolicyStorageError(
            "trust-witness-quorum-policy-storage-target-key-unavailable"
        )
    if (
        envelope.get("authKeyId") == target_auth_key_id
        and checkpoint.get("authKeyId") == target_auth_key_id
    ):
        raise QuorumPolicyStorageError(
            "trust-witness-quorum-policy-storage-rotation-noop"
        )
    state_sha = digest_policy_state(state)
    rotated_envelope = create_envelope(
        state,
        auth_key_id=target_auth_key_id,
    )
    rotated_checkpoint = create_checkpoint(
        state,
        auth_key_id=target_auth_key_id,
    )
    verify_pair(rotated_envelope, rotated_checkpoint)
    if (
        rotated_envelope["stateSha256"] != state_sha
        or rotated_checkpoint["stateSha256"] != state_sha
        or rotated_envelope["state"] != state
    ):
        raise QuorumPolicyStorageError(
            "trust-witness-quorum-policy-storage-rotation-state-changed"
        )
    return {
        "version": 1,
        "receipt": {
            "version": 1,
            "eventType":
                "decision_trace_trust_state_witness_quorum_policy_storage_key_rotation",
            "sourceEnvelopeAuthKeyId": envelope.get("authKeyId"),
            "sourceCheckpointAuthKeyId": checkpoint.get("authKeyId"),
            "targetAuthKeyId": target_auth_key_id,
            "generation": state["generation"],
            "policySha256": state["policySha256"],
            "stateSha256": state_sha,
        },
        "envelope": rotated_envelope,
        "checkpoint": rotated_checkpoint,
    }


def _redis_client(redis_client=None):
    if redis_client is not None:
        return redis_client
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        raise QuorumPolicyStorageError(
            "trust-witness-quorum-policy-storage-redis-unavailable"
        )
    return Redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=3,
        socket_timeout=3,
        health_check_interval=30,
    )


def read_checkpoint(*, redis_client=None) -> dict[str, Any] | None:
    client = _redis_client(redis_client)
    try:
        data = client.hgetall(REDIS_POLICY_CHECKPOINT_KEY)
    except RedisError as exc:
        raise QuorumPolicyStorageError(
            "trust-witness-quorum-policy-storage-redis-unavailable"
        ) from exc
    if not data:
        return None
    raw = data.get("checkpoint_json")
    if not isinstance(raw, str) or not raw:
        raise QuorumPolicyStorageError(
            "trust-witness-quorum-policy-storage-checkpoint-missing"
        )
    try:
        cp = verify_checkpoint(json.loads(raw))
    except Exception as exc:
        if isinstance(exc, QuorumPolicyStorageError):
            raise
        raise QuorumPolicyStorageError(
            "trust-witness-quorum-policy-storage-checkpoint-invalid"
        ) from exc
    if (
        str(data.get("generation") or "") != str(cp["generation"])
        or data.get("policy_sha256") != cp["policySha256"]
        or data.get("state_sha256") != cp["stateSha256"]
    ):
        raise QuorumPolicyStorageError(
            "trust-witness-quorum-policy-storage-checkpoint-mismatch"
        )
    return cp


def persist_checkpoint(
    state: Any,
    *,
    auth_key_id: str | None = None,
    redis_client=None,
) -> dict[str, Any]:
    projected = project_policy_state(state)
    cp = create_checkpoint(projected, auth_key_id=auth_key_id)
    client = _redis_client(redis_client)
    try:
        result = client.eval(
            _CHECKPOINT_CAS,
            1,
            REDIS_POLICY_CHECKPOINT_KEY,
            str(projected["generation"]),
            projected["policySha256"],
            cp["stateSha256"],
            projected["previousPolicySha256"] or "",
            _canonical_json(cp),
        )
    except RedisError as exc:
        raise QuorumPolicyStorageError(
            "trust-witness-quorum-policy-storage-redis-unavailable"
        ) from exc
    code = (
        str(result[0])
        if isinstance(result, (list, tuple)) and result
        else str(result or "")
    )
    if code not in {"created", "refreshed", "advanced"}:
        raise QuorumPolicyStorageError(
            "trust-witness-quorum-policy-storage-checkpoint-cas-"
            + (code or "failed")
        )
    stored = read_checkpoint(redis_client=client)
    if stored is None or stored["stateSha256"] != cp["stateSha256"]:
        raise QuorumPolicyStorageError(
            "trust-witness-quorum-policy-storage-checkpoint-write-unverified"
        )
    return {
        "status": "verified",
        "mode": code,
        "generation": projected["generation"],
        "policy_sha256": projected["policySha256"],
        "state_sha256": cp["stateSha256"],
        "auth_key_id": cp["authKeyId"],
        "independent_retention": "railway-redis-volume",
    }


__all__ = [
    "CHECKPOINT_AUTH_DOMAIN",
    "POLICY_TYPE",
    "QuorumPolicyStorageError",
    "REDIS_POLICY_CHECKPOINT_KEY",
    "STATE_AUTH_DOMAIN",
    "create_checkpoint",
    "create_envelope",
    "digest_policy_state",
    "persist_checkpoint",
    "project_policy_state",
    "read_checkpoint",
    "rotate_pair",
    "serialize_policy_state",
    "verify_checkpoint",
    "verify_envelope",
    "verify_pair",
]
