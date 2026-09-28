import json

import pytest

from services import roster_transition_evidence_mirror as mirror


class FakeRedis:
    def __init__(self):
        self.row = {}

    def hgetall(self, key):
        return dict(self.row) if key == mirror.REDIS_KEY else {}

    def eval(self, _script, _numkeys, key, *args):
        generation, previous, policy, authorization, evidence, checkpoint = args
        generation = int(generation)
        if not self.row:
            if generation != 2:
                return ["bootstrap-generation-invalid"]
            self.row = {
                "generation": str(generation),
                "previous_policy_sha256": previous,
                "policy_sha256": policy,
                "authorization_sha256": authorization,
                "evidence_sha256": evidence,
                "checkpoint_json": checkpoint,
            }
            return ["created"]
        current = int(self.row["generation"])
        if generation < current:
            return ["rollback"]
        if generation == current:
            same = (
                previous == self.row["previous_policy_sha256"]
                and policy == self.row["policy_sha256"]
                and authorization == self.row["authorization_sha256"]
                and evidence == self.row["evidence_sha256"]
            )
            return ["existing"] if same else ["fork"]
        if generation != current + 1:
            return ["generation-gap"]
        if previous != self.row["policy_sha256"]:
            return ["predecessor-policy-mismatch"]
        self.row = {
            "generation": str(generation),
            "previous_policy_sha256": previous,
            "policy_sha256": policy,
            "authorization_sha256": authorization,
            "evidence_sha256": evidence,
            "checkpoint_json": checkpoint,
        }
        return ["advanced"]


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setenv(
        mirror.KEYRING_ENV,
        json.dumps({"evidence-a": "E" * 48}),
    )
    monkeypatch.setenv(mirror.ACTIVE_KEY_ENV, "evidence-a")


def evidence(generation=2, previous="1"*64, policy="2"*64):
    witnesses = ["foundation-project-l", "redis-project-l"]
    rows = []
    for witness, key, tag in (
        (witnesses[0], "foundation-witness-v1", "a"*64),
        (witnesses[1], "roster-transition-a", "b"*64),
    ):
        rows.append({
            "authorizationVersion": 1,
            "authorizationType":
                "decision_trace_trust_state_external_witness_roster_transition",
            "authAlgorithm": "HMAC-SHA-256",
            "witnessId": witness,
            "authKeyId": key,
            "fromGeneration": generation-1,
            "toGeneration": generation,
            "fromPolicySha256": previous,
            "toPolicySha256": policy,
            "authTag": tag,
        })
    return {
        "status": "verified",
        "generation": generation,
        "previousPolicySha256": previous,
        "policySha256": policy,
        "authorizationSha256": "c"*64,
        "authorizingWitnessIds": witnesses,
        "authorizations": rows,
    }


def test_evidence_mirror_bootstraps_at_first_transition():
    redis = FakeRedis()
    result = mirror.ensure_evidence_mirror(evidence(), redis_client=redis)
    assert result["mode"] == "created"
    assert result["generation"] == 2
    assert len(result["evidence_sha256"]) == 64


def test_evidence_mirror_is_idempotent():
    redis = FakeRedis()
    mirror.ensure_evidence_mirror(evidence(), redis_client=redis)
    result = mirror.ensure_evidence_mirror(evidence(), redis_client=redis)
    assert result["mode"] == "existing"


def test_evidence_mirror_detects_same_generation_fork():
    redis = FakeRedis()
    mirror.ensure_evidence_mirror(evidence(), redis_client=redis)
    changed = evidence()
    changed["authorizations"][0]["authTag"] = "f"*64
    with pytest.raises(
        mirror.RosterTransitionEvidenceMirrorError,
        match="external-roster-evidence-mirror-fork",
    ):
        mirror.ensure_evidence_mirror(changed, redis_client=redis)


def test_evidence_mirror_rejects_rollback_and_gap():
    redis = FakeRedis()
    first = evidence()
    mirror.ensure_evidence_mirror(first, redis_client=redis)
    third = evidence(4, previous="3"*64, policy="4"*64)
    with pytest.raises(
        mirror.RosterTransitionEvidenceMirrorError,
        match="generation-gap",
    ):
        mirror.ensure_evidence_mirror(third, redis_client=redis)


def test_checkpoint_hmac_detects_tamper():
    redis = FakeRedis()
    mirror.ensure_evidence_mirror(evidence(), redis_client=redis)
    raw = json.loads(redis.row["checkpoint_json"])
    raw["evidenceSha256"] = "f"*64
    redis.row["checkpoint_json"] = json.dumps(raw)
    with pytest.raises(
        mirror.RosterTransitionEvidenceMirrorError,
        match="auth-failed",
    ):
        mirror.read_mirror(redis_client=redis)
