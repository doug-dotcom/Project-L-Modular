import json

import pytest

from services import external_witness_roster as roster
from services import foundation_roster_head_witness as foundation_head


POLICY_SHA = (
    "a5c456d49e47f1be3f2a7b7ed017328"
    "844484ba05c4e6ef3212412c6361156c4"
)
STATE_SHA = (
    "19818486f5515d0d0e9f2ea86c1a2b12"
    "30abc2db4e0ac47b405566e06d6b6808"
)
CHECKPOINT_SHA = (
    "633fe8e596c47f04f60fb12d1ef61cb"
    "0e86e709d564e475162d9d5c030672611"
)
HEAD_SHA = (
    "7d45840c825f15861bf3368024b36e394"
    "22bd5f66a5f54ef6927bacd05f3cce5"
)
CHAIN_TAG = (
    "2eba8a316ca1dd8a1596040e3ac63799"
    "ebd02deb60adce23afa6c9279f774ce1"
)
HEAD_TAG = (
    "52f950f915382a5be99ed3d888fcc120"
    "29608bc1a6420839e0cf5d4e55b5a7b3"
)


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeHistoryDB:
    def __init__(self):
        self.rpc_calls = []

    def rpc(self, name, params):
        self.rpc_calls.append((name, params))

        class Call:
            def execute(_self):
                if name == "shine_ai_external_witness_roster_history_v1":
                    return FakeResult({
                        "status": "trusted",
                        "generation": 1,
                        "policySha256": POLICY_SHA,
                        "stateSha256": STATE_SHA,
                        "history": [{
                            "generation": 1,
                            "minimumWitnesses": 2,
                            "acceptedWitnessIds": [
                                "foundation-project-l",
                                "redis-project-l",
                            ],
                            "previousPolicySha256": None,
                            "policySha256": POLICY_SHA,
                            "stateSha256": STATE_SHA,
                            "acceptanceMode": "genesis-pin",
                            "authorizationSha256": None,
                            "authorizingWitnessIds": None,
                        }],
                    })
                if name == "concierge_foundation_client_token_v1":
                    return FakeResult("t" * 48)
                raise AssertionError(name)

        return Call()


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.status_code = status_code
        self._payload = payload
        self.content = json.dumps(payload).encode()
        self.headers = {"content-length": str(len(self.content))}

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv(
        "SHINE_TRACE_EXTERNAL_WITNESS_ROSTER_STORAGE_KEYRING_JSON",
        json.dumps({
            "roster-a": "S" * 48,
            "roster-b": "T" * 48,
        }),
    )
    monkeypatch.setenv(
        "SHINE_TRACE_EXTERNAL_WITNESS_ROSTER_STORAGE_ACTIVE_KEY_ID",
        "roster-a",
    )


def test_layer161_genesis_checkpoint_and_head_match_contract_vectors():
    bundle = roster.build_roster_monotonic_head(FakeHistoryDB())
    checkpoint = bundle["checkpoint"]
    head = bundle["head"]

    assert checkpoint["checkpointSha256"] == CHECKPOINT_SHA
    assert checkpoint["authTag"] == CHAIN_TAG
    assert head["headSha256"] == HEAD_SHA
    assert head["authTag"] == HEAD_TAG
    assert head["sequence"] == 1
    assert head["generation"] == 1
    assert head["policySha256"] == POLICY_SHA
    assert head["stateSha256"] == STATE_SHA
    assert roster.verify_roster_chain_record(checkpoint) == checkpoint
    assert roster.verify_roster_monotonic_head(head) == head


def test_storage_key_rotation_does_not_change_roster_head_identity(monkeypatch):
    first = roster.build_roster_monotonic_head(FakeHistoryDB())

    monkeypatch.setenv(
        "SHINE_TRACE_EXTERNAL_WITNESS_ROSTER_STORAGE_ACTIVE_KEY_ID",
        "roster-b",
    )
    second = roster.build_roster_monotonic_head(FakeHistoryDB())

    assert first["checkpoint"]["checkpointSha256"] == second["checkpoint"][
        "checkpointSha256"
    ]
    assert first["head"]["headSha256"] == second["head"]["headSha256"]
    assert first["checkpoint"]["authKeyId"] == "roster-a"
    assert second["checkpoint"]["authKeyId"] == "roster-b"
    assert first["checkpoint"]["authTag"] != second["checkpoint"]["authTag"]
    assert first["head"]["authTag"] != second["head"]["authTag"]


def test_foundation_layer162_receipt_is_projected_without_auth_tag():
    db = FakeHistoryDB()
    head = roster.build_roster_monotonic_head(db)["head"]
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        request = kwargs["json"]
        assert request["operation"] == "external-roster-head-record"
        assert request["headSha256"] == HEAD_SHA
        assert "authTag" not in request
        return FakeResponse({
            "status": "witnessed",
            "replayed": False,
            "witnessVersion": 1,
            "witnessType": foundation_head.WITNESS_TYPE,
            "authAlgorithm": "HMAC-SHA-256",
            "witnessId": foundation_head.WITNESS_ID,
            "authKeyId": "foundation-roster-head-witness-v1",
            "headVersion": 1,
            "sequence": head["sequence"],
            "headSha256": head["headSha256"],
            "generation": head["generation"],
            "policySha256": head["policySha256"],
            "stateSha256": head["stateSha256"],
            "authTag": "a" * 64,
        })

    receipt = foundation_head.ensure_foundation_roster_head_witness(
        db,
        head,
        witness_url="https://foundation.example/witness",
        post_impl=fake_post,
    )

    assert receipt == {
        "status": "verified",
        "witness_id": foundation_head.WITNESS_ID,
        "auth_key_id": "foundation-roster-head-witness-v1",
        "sequence": 1,
        "head_sha256": HEAD_SHA,
        "generation": 1,
        "policy_sha256": POLICY_SHA,
        "state_sha256": STATE_SHA,
        "replayed": False,
        "independent_retention": "foundation-supabase-vault-hmac",
    }
    assert "authTag" not in receipt
    assert len(calls) == 1


def test_foundation_receipt_must_bind_exact_roster_head():
    db = FakeHistoryDB()
    head = roster.build_roster_monotonic_head(db)["head"]

    def fake_post(_url, **_kwargs):
        return FakeResponse({
            "status": "witnessed",
            "witnessVersion": 1,
            "witnessType": foundation_head.WITNESS_TYPE,
            "authAlgorithm": "HMAC-SHA-256",
            "witnessId": foundation_head.WITNESS_ID,
            "authKeyId": "foundation-roster-head-witness-v1",
            "headVersion": 1,
            "sequence": 1,
            "headSha256": "f" * 64,
            "generation": 1,
            "policySha256": POLICY_SHA,
            "stateSha256": STATE_SHA,
            "authTag": "a" * 64,
        })

    with pytest.raises(
        foundation_head.FoundationRosterHeadWitnessError,
        match="foundation-roster-head-witness-response-invalid",
    ):
        foundation_head.ensure_foundation_roster_head_witness(
            db,
            head,
            witness_url="https://foundation.example/witness",
            post_impl=fake_post,
        )



def _raw_foundation_witness(head, auth_key_id, *, replayed=True):
    return {
        "status": "witnessed",
        "replayed": replayed,
        "witnessVersion": 1,
        "witnessType": foundation_head.WITNESS_TYPE,
        "authAlgorithm": "HMAC-SHA-256",
        "witnessId": foundation_head.WITNESS_ID,
        "authKeyId": auth_key_id,
        "headVersion": 1,
        "sequence": head["sequence"],
        "headSha256": head["headSha256"],
        "generation": head["generation"],
        "policySha256": head["policySha256"],
        "stateSha256": head["stateSha256"],
        "authTag": "a" * 64,
    }


def test_layer211_foundation_witness_rotation_preserves_head_and_hides_tag():
    db = FakeHistoryDB()
    head = roster.build_roster_monotonic_head(db)["head"]
    source_key = "foundation-roster-head-witness-v1"
    target_key = "foundation-roster-head-witness-v2"
    calls = []

    def fake_post(_url, **kwargs):
        request = kwargs["json"]
        calls.append(request)
        if request["operation"] == "external-roster-head-current":
            key = source_key if len(calls) == 1 else target_key
            return FakeResponse(
                _raw_foundation_witness(head, key)
            )
        assert request["operation"] == "external-roster-head-rotate"
        assert request["targetAuthKeyId"] == target_key
        witness = _raw_foundation_witness(
            head,
            target_key,
            replayed=False,
        )
        return FakeResponse({
            "status": "rotated",
            "receipt": {
                "version": 1,
                "eventType": (
                    "decision_trace_trust_state_witness_quorum_policy_"
                    "monotonic_head_witness_key_rotation"
                ),
                "witnessId": foundation_head.WITNESS_ID,
                "sourceAuthKeyId": source_key,
                "targetAuthKeyId": target_key,
                "sequence": head["sequence"],
                "headSha256": head["headSha256"],
                "generation": head["generation"],
                "policySha256": head["policySha256"],
                "stateSha256": head["stateSha256"],
            },
            "witness": witness,
        })

    result = foundation_head.rotate_foundation_roster_head_witness(
        db,
        target_key,
        witness_url="https://foundation.example/witness",
        post_impl=fake_post,
    )

    assert result["status"] == "verified"
    assert result["mode"] == "rotated"
    assert result["source_auth_key_id"] == source_key
    assert result["target_auth_key_id"] == target_key
    assert result["head_sha256"] == HEAD_SHA
    assert result["policy_sha256"] == POLICY_SHA
    assert result["state_sha256"] == STATE_SHA
    assert result["state_preserved"] is True
    assert result["witness"]["auth_key_id"] == target_key
    assert "authTag" not in result
    assert "authTag" not in result["witness"]
    assert [row["operation"] for row in calls] == [
        "external-roster-head-current",
        "external-roster-head-rotate",
        "external-roster-head-current",
    ]


def test_layer211_rotation_rejects_truth_substitution():
    db = FakeHistoryDB()
    head = roster.build_roster_monotonic_head(db)["head"]
    source_key = "foundation-roster-head-witness-v1"
    target_key = "foundation-roster-head-witness-v2"
    calls = []

    def fake_post(_url, **kwargs):
        request = kwargs["json"]
        calls.append(request)
        if request["operation"] == "external-roster-head-current":
            return FakeResponse(
                _raw_foundation_witness(head, source_key)
            )

        witness = _raw_foundation_witness(
            head,
            target_key,
            replayed=False,
        )
        return FakeResponse({
            "status": "rotated",
            "receipt": {
                "version": 1,
                "eventType": (
                    "decision_trace_trust_state_witness_quorum_policy_"
                    "monotonic_head_witness_key_rotation"
                ),
                "witnessId": foundation_head.WITNESS_ID,
                "sourceAuthKeyId": source_key,
                "targetAuthKeyId": target_key,
                "sequence": head["sequence"],
                "headSha256": head["headSha256"],
                "generation": head["generation"],
                "policySha256": "f" * 64,
                "stateSha256": head["stateSha256"],
            },
            "witness": witness,
        })

    with pytest.raises(
        foundation_head.FoundationRosterHeadWitnessError,
        match="foundation-roster-head-witness-rotation-response-invalid",
    ):
        foundation_head.rotate_foundation_roster_head_witness(
            db,
            target_key,
            witness_url="https://foundation.example/witness",
            post_impl=fake_post,
        )


def test_layer211_rotation_is_idempotent_when_target_already_bound():
    db = FakeHistoryDB()
    head = roster.build_roster_monotonic_head(db)["head"]
    target_key = "foundation-roster-head-witness-v2"
    calls = []

    def fake_post(_url, **kwargs):
        calls.append(kwargs["json"])
        return FakeResponse(
            _raw_foundation_witness(head, target_key)
        )

    result = foundation_head.rotate_foundation_roster_head_witness(
        db,
        target_key,
        witness_url="https://foundation.example/witness",
        post_impl=fake_post,
    )

    assert result["status"] == "verified"
    assert result["mode"] == "already-rotated"
    assert result["source_auth_key_id"] == target_key
    assert result["target_auth_key_id"] == target_key
    assert result["state_preserved"] is True
    assert len(calls) == 1
