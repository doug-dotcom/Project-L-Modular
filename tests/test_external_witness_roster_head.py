from services import external_witness_roster as roster


POLICY_SHA = (
    "a5c456d49e47f1be3f2a7b7ed017328"
    "844484ba05c4e6ef3212412c6361156c4"
)
STATE_SHA = (
    "19818486f5515d0d0e9f2ea86c1a2b12"
    "30abc2db4e0ac47b405566e06d6b6808"
)
EXPECTED_CHECKPOINT_SHA = (
    "633fe8e596c47f04f60fb12d1ef61cb0"
    "e86e709d564e475162d9d5c030672611"
)
EXPECTED_HEAD_SHA = (
    "7d45840c825f15861bf3368024b36e394"
    "22bd5f66a5f54ef6927bacd05f3cce5"
)


class Result:
    def __init__(self, data):
        self.data = data


class HeadDB:
    def __init__(self, rows):
        self.rows = rows

    def rpc(self, name, params):
        assert name == "shine_ai_external_witness_roster_head_material_v1"
        assert params == {}
        rows = self.rows

        class Call:
            def execute(self):
                return Result({
                    "status": "verified",
                    "historyVersion": 1,
                    "sequence": len(rows),
                    "generation": len(rows),
                    "rows": rows,
                })

        return Call()


def genesis_row():
    return {
        "sequence": 1,
        "generation": 1,
        "previousPolicySha256": None,
        "policySha256": POLICY_SHA,
        "stateSha256": STATE_SHA,
    }


def test_layer161_genesis_head_matches_cross_language_vector():
    head = roster.build_monotonic_roster_head(
        HeadDB([genesis_row()]),
        expected_roster={
            "generation": 1,
            "policySha256": POLICY_SHA,
            "roster_storage_state_sha256": STATE_SHA,
        },
    )

    assert head == {
        "headVersion": 1,
        "headType":
            "decision_trace_trust_state_witness_quorum_policy_"
            "external_head_witness_quorum_monotonic_head",
        "checkpointChainVersion": 1,
        "sequence": 1,
        "checkpointSha256": EXPECTED_CHECKPOINT_SHA,
        "generation": 1,
        "policySha256": POLICY_SHA,
        "stateSha256": STATE_SHA,
        "headSha256": EXPECTED_HEAD_SHA,
    }


def test_roster_head_rejects_current_state_mismatch():
    try:
        roster.build_monotonic_roster_head(
            HeadDB([genesis_row()]),
            expected_roster={
                "generation": 1,
                "policySha256": POLICY_SHA,
                "roster_storage_state_sha256": "0" * 64,
            },
        )
    except roster.ExternalWitnessRosterError as exc:
        assert str(exc) == (
            "external-witness-roster-head-current-state-mismatch"
        )
    else:
        raise AssertionError("mismatched current roster state was accepted")


def test_roster_head_rejects_non_contiguous_policy_chain():
    rows = [
        genesis_row(),
        {
            "sequence": 2,
            "generation": 2,
            "previousPolicySha256": "0" * 64,
            "policySha256": "1" * 64,
            "stateSha256": "2" * 64,
        },
    ]
    try:
        roster.build_monotonic_roster_head(HeadDB(rows))
    except roster.ExternalWitnessRosterError as exc:
        assert str(exc) == (
            "external-witness-roster-head-policy-chain-mismatch"
        )
    else:
        raise AssertionError("broken roster policy chain was accepted")
