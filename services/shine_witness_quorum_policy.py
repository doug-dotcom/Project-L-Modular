"""Persisted witness-quorum policy trust for Project L.

Layer 197 mirrors Shine-AI Layer 149/150 canonical policy semantics for the
witnesses Project L already verifies:
- foundation-project-l (independent Foundation Supabase witness)
- project-l-redis (local monotonic head on persistent Railway Redis)

The initial policy is deliberately 2-of-2. Membership changes are not accepted
by this layer; they require a future previous-quorum-authorised transition
contract rather than runtime/config drift.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
WITNESS_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")

POLICY_TYPE = "decision_trace_trust_state_witness_quorum_policy"
TRUST_STATE_TYPE = POLICY_TYPE

FOUNDATION_WITNESS_ID = "foundation-project-l"
REDIS_WITNESS_ID = "project-l-redis"
GENESIS_ACCEPTED_WITNESS_IDS = (
    FOUNDATION_WITNESS_ID,
    REDIS_WITNESS_ID,
)
GENESIS_MINIMUM_WITNESSES = 2
GENESIS_POLICY_SHA256 = (
    "aac7d1acaec5bf64d5f7d3fe535cbb48"
    "e99df0900eb91e8a8b44cbbfcbb5a92e"
)


class WitnessQuorumPolicyError(RuntimeError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _policy_material(
    *,
    generation: int,
    minimum_witnesses: int,
    accepted_witness_ids: list[str],
    previous_policy_sha256: str | None,
) -> dict[str, Any]:
    return {
        "policyVersion": 1,
        "policyType": POLICY_TYPE,
        "generation": generation,
        "minimumWitnesses": minimum_witnesses,
        "acceptedWitnessIds": accepted_witness_ids,
        "previousPolicySha256": previous_policy_sha256,
    }


def digest_policy_material(policy: Any) -> str:
    projected = project_policy(policy, verify_digest=False)
    material = _policy_material(
        generation=projected["generation"],
        minimum_witnesses=projected["minimumWitnesses"],
        accepted_witness_ids=projected["acceptedWitnessIds"],
        previous_policy_sha256=projected["previousPolicySha256"],
    )
    return hashlib.sha256(
        _canonical_json(material).encode("utf-8")
    ).hexdigest()


def _accepted_ids(value: Any) -> list[str]:
    if (
        not isinstance(value, list)
        or not 2 <= len(value) <= 4
    ):
        raise WitnessQuorumPolicyError("witness-quorum-policy-invalid")
    ids: list[str] = []
    for item in value:
        if (
            not isinstance(item, str)
            or WITNESS_ID_RE.fullmatch(item) is None
        ):
            raise WitnessQuorumPolicyError(
                "witness-quorum-policy-invalid"
            )
        ids.append(item)
    if len(set(ids)) != len(ids) or ids != sorted(ids):
        raise WitnessQuorumPolicyError("witness-quorum-policy-invalid")
    return ids


def project_policy(
    value: Any,
    *,
    verify_digest: bool = True,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WitnessQuorumPolicyError("witness-quorum-policy-invalid")
    generation = value.get("generation")
    minimum = value.get("minimumWitnesses")
    ids = _accepted_ids(value.get("acceptedWitnessIds"))
    previous = value.get("previousPolicySha256")
    policy_sha = value.get("policySha256")
    if (
        value.get("policyVersion") != 1
        or value.get("policyType") != POLICY_TYPE
        or not isinstance(generation, int)
        or isinstance(generation, bool)
        or not 1 <= generation <= 1_000_000
        or not isinstance(minimum, int)
        or isinstance(minimum, bool)
        or not 2 <= minimum <= len(ids)
        or not isinstance(policy_sha, str)
        or SHA256_RE.fullmatch(policy_sha) is None
    ):
        raise WitnessQuorumPolicyError("witness-quorum-policy-invalid")
    if generation == 1:
        if previous is not None:
            raise WitnessQuorumPolicyError(
                "witness-quorum-policy-invalid"
            )
    elif (
        not isinstance(previous, str)
        or SHA256_RE.fullmatch(previous) is None
    ):
        raise WitnessQuorumPolicyError("witness-quorum-policy-invalid")

    projected = {
        "policyVersion": 1,
        "policyType": POLICY_TYPE,
        "generation": generation,
        "minimumWitnesses": minimum,
        "acceptedWitnessIds": ids,
        "previousPolicySha256": previous,
        "policySha256": policy_sha,
    }
    if verify_digest:
        computed = digest_policy_material(projected)
        if computed != policy_sha:
            raise WitnessQuorumPolicyError(
                "witness-quorum-policy-fingerprint-invalid"
            )
    return projected


def genesis_policy() -> dict[str, Any]:
    material = _policy_material(
        generation=1,
        minimum_witnesses=GENESIS_MINIMUM_WITNESSES,
        accepted_witness_ids=list(GENESIS_ACCEPTED_WITNESS_IDS),
        previous_policy_sha256=None,
    )
    digest = hashlib.sha256(
        _canonical_json(material).encode("utf-8")
    ).hexdigest()
    if digest != GENESIS_POLICY_SHA256:
        raise WitnessQuorumPolicyError(
            "witness-quorum-genesis-pin-invalid"
        )
    return {
        **material,
        "policySha256": digest,
    }


def project_policy_trust_state(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WitnessQuorumPolicyError(
            "witness-quorum-policy-trust-invalid"
        )
    state = {
        "trustStateVersion": value.get("trustStateVersion"),
        "trustStateType": value.get("trustStateType"),
        "generation": value.get("generation"),
        "minimumWitnesses": value.get("minimumWitnesses"),
        "acceptedWitnessIds": value.get("acceptedWitnessIds"),
        "previousPolicySha256": value.get("previousPolicySha256"),
        "policySha256": value.get("policySha256"),
    }
    if (
        state["trustStateVersion"] != 1
        or state["trustStateType"] != TRUST_STATE_TYPE
    ):
        raise WitnessQuorumPolicyError(
            "witness-quorum-policy-trust-invalid"
        )
    policy = project_policy({
        "policyVersion": 1,
        "policyType": POLICY_TYPE,
        "generation": state["generation"],
        "minimumWitnesses": state["minimumWitnesses"],
        "acceptedWitnessIds": state["acceptedWitnessIds"],
        "previousPolicySha256": state["previousPolicySha256"],
        "policySha256": state["policySha256"],
    })
    return {
        "trustStateVersion": 1,
        "trustStateType": TRUST_STATE_TYPE,
        "generation": policy["generation"],
        "minimumWitnesses": policy["minimumWitnesses"],
        "acceptedWitnessIds": policy["acceptedWitnessIds"],
        "previousPolicySha256": policy["previousPolicySha256"],
        "policySha256": policy["policySha256"],
    }


def genesis_policy_trust_state() -> dict[str, Any]:
    policy = genesis_policy()
    return {
        "trustStateVersion": 1,
        "trustStateType": TRUST_STATE_TYPE,
        "generation": 1,
        "minimumWitnesses": policy["minimumWitnesses"],
        "acceptedWitnessIds": policy["acceptedWitnessIds"],
        "previousPolicySha256": None,
        "policySha256": policy["policySha256"],
    }


def load_or_bootstrap_policy_trust(db) -> dict[str, Any]:
    try:
        result = db.rpc(
            "shine_ai_witness_quorum_policy_snapshot_v1",
            {},
        ).execute()
    except Exception as exc:
        raise WitnessQuorumPolicyError(
            "witness-quorum-policy-snapshot-unavailable"
        ) from exc
    payload = result.data if isinstance(result.data, dict) else {}
    status = str(payload.get("status") or "")
    if status == "unbootstrapped":
        try:
            result = db.rpc(
                "shine_ai_witness_quorum_policy_bootstrap_v1",
                {},
            ).execute()
        except Exception as exc:
            raise WitnessQuorumPolicyError(
                "witness-quorum-policy-bootstrap-failed"
            ) from exc
        payload = result.data if isinstance(result.data, dict) else {}
        status = str(payload.get("status") or "")

    if status not in {"trusted", "already_trusted"}:
        raise WitnessQuorumPolicyError(
            str(
                payload.get("reason_code")
                or "witness-quorum-policy-storage-invalid"
            )
        )

    state = project_policy_trust_state(payload.get("trust_state"))
    # Layer 197 is deliberately genesis-only. A different generation or
    # fingerprint must not become trusted until a previous-quorum transition
    # contract is implemented.
    genesis = genesis_policy_trust_state()
    if state != genesis:
        if state["generation"] < genesis["generation"]:
            reason = "witness-quorum-policy-rollback-detected"
        elif state["generation"] == genesis["generation"]:
            reason = "witness-quorum-policy-equivocation-detected"
        else:
            reason = "witness-quorum-policy-transition-unimplemented"
        raise WitnessQuorumPolicyError(reason)
    return state


def evaluate_witness_quorum(
    policy_trust_state: Any,
    *,
    foundation_witness: Any,
    local_witness: Any,
) -> dict[str, Any]:
    state = project_policy_trust_state(policy_trust_state)
    candidates = {
        FOUNDATION_WITNESS_ID: (
            foundation_witness
            if isinstance(foundation_witness, dict)
            else {}
        ),
        REDIS_WITNESS_ID: (
            local_witness
            if isinstance(local_witness, dict)
            else {}
        ),
    }

    verified: list[str] = []
    anchor = None
    for witness_id in state["acceptedWitnessIds"]:
        item = candidates.get(witness_id, {})
        if (
            item.get("status") != "verified"
            or item.get("witness_id") != witness_id
        ):
            continue
        identity = (
            item.get("sequence"),
            item.get("head_sha256"),
            item.get("generation"),
            item.get("keyset_sha256"),
            item.get("state_sha256"),
        )
        if anchor is None:
            anchor = identity
        elif identity != anchor:
            raise WitnessQuorumPolicyError(
                "witness-quorum-head-mismatch"
            )
        verified.append(witness_id)

    if len(verified) < state["minimumWitnesses"]:
        raise WitnessQuorumPolicyError(
            "witness-quorum-insufficient"
        )
    return {
        "status": "verified",
        "policy_generation": state["generation"],
        "policy_sha256": state["policySha256"],
        "minimum_witnesses": state["minimumWitnesses"],
        "accepted_witness_ids": list(state["acceptedWitnessIds"]),
        "verified_witness_ids": sorted(verified),
        "verified_count": len(verified),
    }


__all__ = [
    "FOUNDATION_WITNESS_ID",
    "GENESIS_ACCEPTED_WITNESS_IDS",
    "GENESIS_MINIMUM_WITNESSES",
    "GENESIS_POLICY_SHA256",
    "POLICY_TYPE",
    "REDIS_WITNESS_ID",
    "TRUST_STATE_TYPE",
    "WitnessQuorumPolicyError",
    "digest_policy_material",
    "evaluate_witness_quorum",
    "genesis_policy",
    "genesis_policy_trust_state",
    "load_or_bootstrap_policy_trust",
    "project_policy",
    "project_policy_trust_state",
]
