"""Bounded witness quorum for Project L's monotonic Shine-AI trust head.

Layer 198 counts two independently retained witnesses:
- redis-project-l: private Railway Redis volume, separately HMAC-keyed
- foundation-project-l: separate Foundation Supabase project

The quorum policy is caller-owned deployment configuration, not data supplied by
either witness. Witness HMAC tags never enter the human/runtime trace.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from typing import Any

from redis.exceptions import RedisError

from services.foundation_trust_witness import (
    FoundationWitnessError,
    ensure_foundation_trust_witness,
)
from services.shine_trust_storage import (
    TrustStorageError,
    _redis_client,
    prepare_monotonic_head,
)

SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
KEY_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")

REDIS_WITNESS_ID = "redis-project-l"
FOUNDATION_WITNESS_ID = "foundation-project-l"
WITNESS_TYPE = "decision_trace_trust_state_monotonic_head_witness"
WITNESS_AUTH_DOMAIN = (
    "shine-ai:decision-trace-trust-state-monotonic-head-witness:v1"
)
QUORUM_POLICY_TYPE = "decision_trace_trust_state_witness_quorum_policy"
CERTIFIED_GENESIS_POLICY_SHA256 = (
    "26b6d1a3b4183cfa596f8c9c06c18e73"
    "aa0eda6a80a6362649130e9357bf220e"
)
REDIS_WITNESS_KEY = "shine:project-l:trace-trust:witness:redis:v1"

_REDIS_WITNESS_CAS = r"""
local key = KEYS[1]
local next_sequence = tonumber(ARGV[1])
local next_head_sha = ARGV[2]
local next_generation = tonumber(ARGV[3])
local next_keyset_sha = ARGV[4]
local next_state_sha = ARGV[5]
local witness_json = ARGV[6]

local current_sequence_raw = redis.call('HGET', key, 'sequence')
if not current_sequence_raw then
  if next_sequence < 1 then
    return {'bootstrap-invalid'}
  end
  redis.call(
    'HSET',
    key,
    'sequence', tostring(next_sequence),
    'head_sha256', next_head_sha,
    'generation', tostring(next_generation),
    'keyset_sha256', next_keyset_sha,
    'state_sha256', next_state_sha,
    'witness_json', witness_json
  )
  return {'created'}
end

local current_sequence = tonumber(current_sequence_raw)
local current_head_sha = redis.call('HGET', key, 'head_sha256') or ''
local current_generation = tonumber(redis.call('HGET', key, 'generation') or '0')
local current_keyset_sha = redis.call('HGET', key, 'keyset_sha256') or ''
local current_state_sha = redis.call('HGET', key, 'state_sha256') or ''

if next_sequence < current_sequence then
  return {'rollback'}
end

if next_sequence == current_sequence then
  if next_head_sha == current_head_sha
     and next_generation == current_generation
     and next_keyset_sha == current_keyset_sha
     and next_state_sha == current_state_sha then
    return {'existing'}
  end
  return {'equivocation'}
end

if next_sequence ~= current_sequence + 1 then
  return {'sequence-gap'}
end
if next_generation < current_generation
   or next_generation > current_generation + 1 then
  return {'generation-invalid'}
end
if next_generation == current_generation
   and next_keyset_sha ~= current_keyset_sha then
  return {'keyset-equivocation'}
end
if next_generation == current_generation + 1
   and next_keyset_sha == current_keyset_sha then
  return {'generation-without-keyset-change'}
end
if next_state_sha == current_state_sha then
  return {'state-not-advanced'}
end

redis.call(
  'HSET',
  key,
  'sequence', tostring(next_sequence),
  'head_sha256', next_head_sha,
  'generation', tostring(next_generation),
  'keyset_sha256', next_keyset_sha,
  'state_sha256', next_state_sha,
  'witness_json', witness_json
)
return {'advanced'}
"""


class WitnessQuorumError(RuntimeError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hmac_sha256(secret: str, value: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _redis_witness_keyring() -> tuple[str, dict[str, str]]:
    raw = os.getenv("SHINE_TRACE_REDIS_WITNESS_KEYRING_JSON", "").strip()
    active = os.getenv("SHINE_TRACE_REDIS_WITNESS_ACTIVE_KEY_ID", "").strip()
    if not raw or KEY_ID_RE.fullmatch(active) is None:
        raise WitnessQuorumError("redis-witness-keyring-unavailable")
    try:
        parsed = json.loads(raw)
    except Exception as exc:
        raise WitnessQuorumError("redis-witness-keyring-invalid") from exc
    if not isinstance(parsed, dict) or not 1 <= len(parsed) <= 4:
        raise WitnessQuorumError("redis-witness-keyring-invalid")
    keyring: dict[str, str] = {}
    for raw_key, raw_secret in parsed.items():
        key_id = str(raw_key)
        if (
            KEY_ID_RE.fullmatch(key_id) is None
            or not isinstance(raw_secret, str)
            or len(raw_secret) < 32
            or len(raw_secret) > 8192
        ):
            raise WitnessQuorumError("redis-witness-keyring-invalid")
        keyring[key_id] = raw_secret
    if active not in keyring:
        raise WitnessQuorumError("redis-witness-active-key-unavailable")
    return active, keyring


def _redis_witness_secret(key_id: str) -> str:
    _active, keyring = _redis_witness_keyring()
    secret = keyring.get(key_id)
    if secret is None:
        raise WitnessQuorumError("redis-witness-auth-key-retired")
    return secret


def _witness_material(
    witness_id: str,
    head: dict[str, Any],
) -> dict[str, Any]:
    return {
        "witnessVersion": 1,
        "witnessType": WITNESS_TYPE,
        "witnessId": witness_id,
        "headVersion": 1,
        "sequence": head["sequence"],
        "headSha256": head["headSha256"],
        "generation": head["generation"],
        "keyset_sha256": head["keyset_sha256"],
        "stateSha256": head["stateSha256"],
    }


def create_redis_witness(
    head: dict[str, Any],
    *,
    auth_key_id: str | None = None,
) -> dict[str, Any]:
    active, keyring = _redis_witness_keyring()
    key_id = auth_key_id or active
    if KEY_ID_RE.fullmatch(key_id) is None or key_id not in keyring:
        raise WitnessQuorumError("redis-witness-auth-key-unavailable")
    material = _witness_material(REDIS_WITNESS_ID, head)
    serialized = _canonical_json(material)
    return {
        **material,
        "authAlgorithm": "HMAC-SHA-256",
        "authKeyId": key_id,
        "authTag": _hmac_sha256(
            keyring[key_id],
            WITNESS_AUTH_DOMAIN + "\n" + key_id + "\n" + serialized,
        ),
    }


def verify_witness(
    value: Any,
    *,
    expected_witness_id: str,
    secret_resolver,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WitnessQuorumError("trust-witness-invalid")
    required = (
        "witnessVersion",
        "witnessType",
        "authAlgorithm",
        "witnessId",
        "authKeyId",
        "headVersion",
        "sequence",
        "headSha256",
        "generation",
        "keyset_sha256",
        "stateSha256",
        "authTag",
    )
    if any(key not in value for key in required):
        raise WitnessQuorumError("trust-witness-invalid")

    witness_id = value.get("witnessId")
    key_id = value.get("authKeyId")
    sequence = value.get("sequence")
    generation = value.get("generation")
    hashes = (
        value.get("headSha256"),
        value.get("keyset_sha256"),
        value.get("stateSha256"),
        value.get("authTag"),
    )
    if (
        value.get("witnessVersion") != 1
        or value.get("witnessType") != WITNESS_TYPE
        or value.get("authAlgorithm") != "HMAC-SHA-256"
        or witness_id != expected_witness_id
        or not isinstance(key_id, str)
        or KEY_ID_RE.fullmatch(key_id) is None
        or value.get("headVersion") != 1
        or not isinstance(sequence, int)
        or isinstance(sequence, bool)
        or sequence < 1
        or sequence > 10_000_000
        or not isinstance(generation, int)
        or isinstance(generation, bool)
        or generation < 1
        or generation > 1_000_000
        or any(
            not isinstance(item, str)
            or SHA256_RE.fullmatch(item) is None
            for item in hashes
        )
    ):
        raise WitnessQuorumError("trust-witness-invalid")

    material = {
        "witnessVersion": 1,
        "witnessType": WITNESS_TYPE,
        "witnessId": witness_id,
        "headVersion": 1,
        "sequence": sequence,
        "headSha256": value["headSha256"],
        "generation": generation,
        "keyset_sha256": value["keyset_sha256"],
        "stateSha256": value["stateSha256"],
    }
    expected = _hmac_sha256(
        secret_resolver(key_id),
        WITNESS_AUTH_DOMAIN
        + "\n"
        + key_id
        + "\n"
        + _canonical_json(material),
    )
    if not hmac.compare_digest(expected, value["authTag"]):
        raise WitnessQuorumError("trust-witness-auth-failed")
    return {key: value[key] for key in required}


def _matches_head(witness: dict, head: dict) -> bool:
    return (
        witness["sequence"] == head["sequence"]
        and witness["headSha256"] == head["headSha256"]
        and witness["generation"] == head["generation"]
        and witness["keyset_sha256"] == head["keyset_sha256"]
        and witness["stateSha256"] == head["stateSha256"]
    )


def read_redis_witness(*, redis_client=None) -> dict[str, Any] | None:
    client = _redis_client(redis_client)
    try:
        data = client.hgetall(REDIS_WITNESS_KEY)
    except RedisError as exc:
        raise WitnessQuorumError("redis-witness-unavailable") from exc
    if not data:
        return None
    raw = data.get("witness_json")
    if not isinstance(raw, str) or not raw:
        raise WitnessQuorumError("redis-witness-storage-invalid")
    try:
        value = json.loads(raw)
    except Exception as exc:
        raise WitnessQuorumError("redis-witness-storage-invalid") from exc
    verified = verify_witness(
        value,
        expected_witness_id=REDIS_WITNESS_ID,
        secret_resolver=_redis_witness_secret,
    )
    if (
        str(data.get("sequence") or "") != str(verified["sequence"])
        or data.get("head_sha256") != verified["headSha256"]
        or str(data.get("generation") or "") != str(verified["generation"])
        or data.get("keyset_sha256") != verified["keyset_sha256"]
        or data.get("state_sha256") != verified["stateSha256"]
    ):
        raise WitnessQuorumError("redis-witness-storage-mismatch")
    return verified


def ensure_redis_trust_witness(
    state: Any,
    *,
    redis_client=None,
) -> dict[str, Any]:
    try:
        local = prepare_monotonic_head(
            state,
            redis_client=redis_client,
        )
    except TrustStorageError as exc:
        raise WitnessQuorumError(str(exc)) from exc
    head = local.get("head")
    if not isinstance(head, dict):
        raise WitnessQuorumError("redis-witness-local-head-invalid")

    candidate = create_redis_witness(head)
    client = _redis_client(redis_client)
    try:
        result = client.eval(
            _REDIS_WITNESS_CAS,
            1,
            REDIS_WITNESS_KEY,
            str(candidate["sequence"]),
            candidate["headSha256"],
            str(candidate["generation"]),
            candidate["keyset_sha256"],
            candidate["stateSha256"],
            _canonical_json(candidate),
        )
    except RedisError as exc:
        raise WitnessQuorumError("redis-witness-unavailable") from exc

    code = (
        str(result[0])
        if isinstance(result, (list, tuple)) and result
        else str(result or "")
    )
    if code not in {"created", "existing", "advanced"}:
        raise WitnessQuorumError(
            "redis-witness-cas-" + (code or "failed")
        )

    stored = read_redis_witness(redis_client=client)
    if stored is None or not _matches_head(stored, head):
        raise WitnessQuorumError("redis-witness-commit-mismatch")
    return {
        "status": "verified",
        "witness_id": REDIS_WITNESS_ID,
        "sequence": stored["sequence"],
        "head_sha256": stored["headSha256"],
        "generation": stored["generation"],
        "keyset_sha256": stored["keyset_sha256"],
        "state_sha256": stored["stateSha256"],
        "auth_key_id": stored["authKeyId"],
        "mode": code,
        "independent_retention": "railway-redis-volume",
    }


def _project_quorum_policy(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WitnessQuorumError("trust-witness-quorum-policy-invalid")

    ids = value.get("acceptedWitnessIds")
    minimum = value.get("minimumWitnesses")
    generation = value.get("generation")
    previous = value.get("previousPolicySha256")
    policy_sha = value.get("policySha256")
    if (
        value.get("policyVersion") != 1
        or value.get("policyType") != QUORUM_POLICY_TYPE
        or not isinstance(generation, int)
        or isinstance(generation, bool)
        or not 1 <= generation <= 1_000_000
        or not isinstance(ids, list)
        or not 2 <= len(ids) <= 4
        or ids != sorted(ids)
        or len(set(ids)) != len(ids)
        or any(
            not isinstance(item, str)
            or KEY_ID_RE.fullmatch(item) is None
            for item in ids
        )
        or not isinstance(minimum, int)
        or isinstance(minimum, bool)
        or minimum < 2
        or minimum > len(ids)
        or not isinstance(policy_sha, str)
        or SHA256_RE.fullmatch(policy_sha) is None
    ):
        raise WitnessQuorumError("trust-witness-quorum-policy-invalid")

    if generation == 1:
        if previous is not None:
            raise WitnessQuorumError(
                "trust-witness-quorum-policy-invalid"
            )
    elif (
        not isinstance(previous, str)
        or SHA256_RE.fullmatch(previous) is None
    ):
        raise WitnessQuorumError("trust-witness-quorum-policy-invalid")

    material = {
        "policyVersion": 1,
        "policyType": QUORUM_POLICY_TYPE,
        "generation": generation,
        "minimumWitnesses": minimum,
        "acceptedWitnessIds": list(ids),
        "previousPolicySha256": previous,
    }
    if _sha256_text(_canonical_json(material)) != policy_sha:
        raise WitnessQuorumError(
            "trust-witness-quorum-policy-digest-mismatch"
        )
    return {**material, "policySha256": policy_sha}


def _deployment_quorum_policy_candidate() -> dict[str, Any] | None:
    raw = os.getenv("SHINE_TRACE_WITNESS_QUORUM_POLICY_JSON", "").strip()
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except Exception as exc:
        raise WitnessQuorumError(
            "trust-witness-quorum-policy-invalid"
        ) from exc
    return _project_quorum_policy(value)


def load_quorum_policy() -> dict[str, Any]:
    """Load the Layer 198 deployment pin.

    This remains the out-of-band genesis candidate. Layer 199 persists the
    accepted policy separately and no longer treats this value as the ongoing
    source of truth.
    """
    policy = _deployment_quorum_policy_candidate()
    if policy is None:
        raise WitnessQuorumError(
            "trust-witness-quorum-policy-unavailable"
        )
    if (
        policy["generation"] != 1
        or policy["minimumWitnesses"] != 2
        or policy["acceptedWitnessIds"]
        != sorted([FOUNDATION_WITNESS_ID, REDIS_WITNESS_ID])
        or policy["previousPolicySha256"] is not None
        or policy["policySha256"] != CERTIFIED_GENESIS_POLICY_SHA256
    ):
        raise WitnessQuorumError(
            "trust-witness-quorum-policy-not-certified"
        )
    return policy


def _project_policy_trust_state(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WitnessQuorumError(
            "trust-witness-quorum-policy-trust-invalid"
        )
    if (
        value.get("trustStateVersion") != 1
        or value.get("trustStateType") != QUORUM_POLICY_TYPE
    ):
        raise WitnessQuorumError(
            "trust-witness-quorum-policy-trust-invalid"
        )

    policy = _project_quorum_policy({
        "policyVersion": 1,
        "policyType": QUORUM_POLICY_TYPE,
        "generation": value.get("generation"),
        "minimumWitnesses": value.get("minimumWitnesses"),
        "acceptedWitnessIds": value.get("acceptedWitnessIds"),
        "previousPolicySha256": value.get("previousPolicySha256"),
        "policySha256": value.get("policySha256"),
    })
    return {
        "trustStateVersion": 1,
        "trustStateType": QUORUM_POLICY_TYPE,
        "generation": policy["generation"],
        "minimumWitnesses": policy["minimumWitnesses"],
        "acceptedWitnessIds": policy["acceptedWitnessIds"],
        "previousPolicySha256": policy["previousPolicySha256"],
        "policySha256": policy["policySha256"],
    }


def _policy_from_trust_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "policyVersion": 1,
        "policyType": QUORUM_POLICY_TYPE,
        "generation": state["generation"],
        "minimumWitnesses": state["minimumWitnesses"],
        "acceptedWitnessIds": list(state["acceptedWitnessIds"]),
        "previousPolicySha256": state["previousPolicySha256"],
        "policySha256": state["policySha256"],
    }


def load_persisted_quorum_policy(db) -> dict[str, Any]:
    """Load monotonic quorum-policy trust from Project L's durable store."""
    try:
        result = db.rpc(
            "shine_ai_witness_quorum_policy_snapshot_v1",
            {},
        ).execute()
    except Exception as exc:
        raise WitnessQuorumError(
            "trust-witness-quorum-policy-snapshot-unavailable"
        ) from exc

    payload = result.data if isinstance(result.data, dict) else {}
    status = str(payload.get("status") or "")
    if status == "unbootstrapped":
        # Genesis can only be established from the certified deployment pin.
        load_quorum_policy()
        try:
            result = db.rpc(
                "shine_ai_witness_quorum_policy_bootstrap_v1",
                {},
            ).execute()
        except Exception as exc:
            raise WitnessQuorumError(
                "trust-witness-quorum-policy-bootstrap-failed"
            ) from exc
        payload = result.data if isinstance(result.data, dict) else {}
        status = str(payload.get("status") or "")

    if status not in {"trusted", "already_trusted"}:
        raise WitnessQuorumError(
            str(
                payload.get("reason_code")
                or "trust-witness-quorum-policy-storage-invalid"
            )
        )

    state = _project_policy_trust_state(payload.get("trust_state"))
    policy = _policy_from_trust_state(state)

    # Layer 199 has no membership-transition acceptance path. Anything other
    # than the certified genesis state is therefore fail-closed.
    if (
        state["generation"] != 1
        or state["minimumWitnesses"] != 2
        or state["acceptedWitnessIds"]
        != sorted([FOUNDATION_WITNESS_ID, REDIS_WITNESS_ID])
        or state["previousPolicySha256"] is not None
        or state["policySha256"] != CERTIFIED_GENESIS_POLICY_SHA256
    ):
        raise WitnessQuorumError(
            "trust-witness-quorum-policy-persisted-state-uncertified"
        )

    candidate = _deployment_quorum_policy_candidate()
    if candidate is not None:
        if candidate["generation"] < state["generation"]:
            raise WitnessQuorumError(
                "trust-witness-quorum-policy-rollback-detected"
            )
        if candidate["generation"] == state["generation"]:
            if candidate != policy:
                raise WitnessQuorumError(
                    "trust-witness-quorum-policy-equivocation-detected"
                )
        elif candidate["generation"] > state["generation"] + 1:
            raise WitnessQuorumError(
                "trust-witness-quorum-policy-generation-skip"
            )
        else:
            raise WitnessQuorumError(
                "trust-witness-quorum-policy-transition-unimplemented"
            )

    return {
        **policy,
        "policy_trust_persisted": True,
        "policy_trust_source": "project-l-supabase",
        "policy_trust_generation": state["generation"],
    }


def _foundation_chain_receipt(witness: Any) -> dict[str, Any]:
    if not isinstance(witness, dict):
        raise WitnessQuorumError("trust-witness-foundation-chain-invalid")

    sequence = witness.get("sequence")
    chain_version = witness.get("chain_version")
    previous_chain_tag = witness.get("previous_chain_tag")
    chain_tag = witness.get("chain_tag")
    if (
        witness.get("witness_id") != FOUNDATION_WITNESS_ID
        or witness.get("history_status") != "verified"
        or chain_version != 1
        or not isinstance(sequence, int)
        or isinstance(sequence, bool)
        or sequence < 1
        or not isinstance(previous_chain_tag, str)
        or SHA256_RE.fullmatch(previous_chain_tag) is None
        or not isinstance(chain_tag, str)
        or SHA256_RE.fullmatch(chain_tag) is None
        or (
            sequence == 1
            and previous_chain_tag != "0" * 64
        )
    ):
        raise WitnessQuorumError(
            "trust-witness-foundation-chain-invalid"
        )

    return {
        "status": "verified",
        "witness_id": FOUNDATION_WITNESS_ID,
        "chain_version": chain_version,
        "sequence": sequence,
        "previous_chain_tag": previous_chain_tag,
        "chain_tag": chain_tag,
    }


def ensure_trust_witness_quorum(
    db,
    state: Any,
    *,
    redis_client=None,
    foundation_get_impl=None,
    foundation_post_impl=None,
) -> dict[str, Any]:
    policy = load_persisted_quorum_policy(db)
    try:
        redis_witness = ensure_redis_trust_witness(
            state,
            redis_client=redis_client,
        )
    except WitnessQuorumError:
        raise

    try:
        foundation_witness = ensure_foundation_trust_witness(
            db,
            state,
            redis_client=redis_client,
            get_impl=foundation_get_impl,
            post_impl=foundation_post_impl,
        )
    except FoundationWitnessError as exc:
        raise WitnessQuorumError(str(exc)) from exc

    witnesses = [redis_witness, foundation_witness]
    by_id: dict[str, dict] = {}
    for witness in witnesses:
        witness_id = witness.get("witness_id")
        if (
            not isinstance(witness_id, str)
            or witness_id not in policy["acceptedWitnessIds"]
            or witness_id in by_id
            or witness.get("status") != "verified"
        ):
            raise WitnessQuorumError("trust-witness-quorum-invalid-member")
        by_id[witness_id] = witness

    if len(by_id) < policy["minimumWitnesses"]:
        raise WitnessQuorumError("trust-witness-quorum-insufficient")

    first = next(iter(by_id.values()))
    for witness in by_id.values():
        if (
            witness["sequence"] != first["sequence"]
            or witness["head_sha256"] != first["head_sha256"]
            or witness["generation"] != first["generation"]
            or witness["keyset_sha256"] != first["keyset_sha256"]
            or witness["state_sha256"] != first["state_sha256"]
        ):
            raise WitnessQuorumError("trust-witness-quorum-disagreement")

    foundation_chain = _foundation_chain_receipt(
        by_id[FOUNDATION_WITNESS_ID]
    )
    if foundation_chain["sequence"] != first["sequence"]:
        raise WitnessQuorumError(
            "trust-witness-foundation-chain-sequence-mismatch"
        )

    return {
        "status": "verified",
        "policy_generation": policy["generation"],
        "policy_sha256": policy["policySha256"],
        "policy_trust_persisted": policy["policy_trust_persisted"],
        "policy_trust_source": policy["policy_trust_source"],
        "policy_trust_generation": policy["policy_trust_generation"],
        "minimum_witnesses": policy["minimumWitnesses"],
        "verified_witness_count": len(by_id),
        "witness_ids": sorted(by_id),
        "sequence": first["sequence"],
        "head_sha256": first["head_sha256"],
        "generation": first["generation"],
        "keyset_sha256": first["keyset_sha256"],
        "state_sha256": first["state_sha256"],
        "independence": [
            by_id[item]["independent_retention"]
            for item in sorted(by_id)
        ],
        "foundation_chain": foundation_chain,
    }


__all__ = [
    "CERTIFIED_GENESIS_POLICY_SHA256",
    "FOUNDATION_WITNESS_ID",
    "QUORUM_POLICY_TYPE",
    "REDIS_WITNESS_ID",
    "REDIS_WITNESS_KEY",
    "WitnessQuorumError",
    "create_redis_witness",
    "ensure_redis_trust_witness",
    "ensure_trust_witness_quorum",
    "load_persisted_quorum_policy",
    "load_quorum_policy",
    "read_redis_witness",
    "verify_witness",
]
