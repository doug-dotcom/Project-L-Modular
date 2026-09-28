from pathlib import Path


SQL = Path(
    "contracts/foundation/"
    "project_l_external_roster_head_witness_v1.sql"
)
ROTATION_SQL = Path(
    "contracts/foundation/"
    "project_l_external_roster_head_witness_rotation_v2.sql"
)
EDGE = Path(
    "contracts/foundation/project-l-trust-witness/index.ts"
)


def sql() -> str:
    return SQL.read_text(encoding="utf-8").lower()


def rotation_sql() -> str:
    return ROTATION_SQL.read_text(encoding="utf-8").lower()


def edge() -> str:
    return EDGE.read_text(encoding="utf-8").lower()


def test_foundation_roster_head_witness_uses_separate_vault_domain():
    value = sql()

    assert "project_l_external_roster_head_witness_hmac_v1" in value
    assert "project_l_roster_head_witness_state" in value
    assert "project_l_roster_head_witness_events" in value
    assert (
        "shine-ai:decision-trace-trust-state-witness-quorum-policy-"
        "external-head-witness-quorum-monotonic-head-witness:v1"
        in value
    )
    assert "foundation-roster-head-witness-v1" in value


def test_foundation_roster_head_witness_is_high_water_and_idempotent():
    value = sql()

    assert "roster-head-witness-sequence-rollback" in value
    assert "roster-head-witness-sequence-equivocation" in value
    assert "roster-head-witness-sequence-skip" in value
    assert "roster-head-witness-generation-without-policy-change" in value
    assert "roster-head-witness-state-not-advanced" in value
    assert "'replayed',true" in value
    assert "for update" in value


def test_foundation_roster_head_tables_are_not_directly_exposed():
    value = " ".join(sql().split())

    assert "enable row level security" in value
    assert "revoke all on foundation.project_l_roster_head_witness_state" in value
    assert "revoke all on foundation.project_l_roster_head_witness_events" in value
    assert (
        "grant execute on function "
        "foundation.project_l_roster_head_witness_record_v1"
        in value
    )
    assert "to foundation_gateway" in value


def test_foundation_edge_exposes_only_bounded_roster_head_operations():
    value = edge()

    assert "external-roster-head-current" in value
    assert "external-roster-head-record" in value
    assert "project_l_roster_head_witness_current_v1" in value
    assert "project_l_roster_head_witness_record_v1" in value
    assert "set local role foundation_gateway" in value
    assert "decrypted_secret" not in value



def test_layer211_roster_head_witness_supports_overlap_rotation():
    value = " ".join(rotation_sql().split())

    assert "project_l_external_roster_head_witness_hmac_v2" in value
    assert "foundation-roster-head-witness-v1" in value
    assert "foundation-roster-head-witness-v2" in value
    assert (
        "unique (witness_id,sequence,auth_key_id)"
        in value
    )
    assert "project_l_roster_head_witness_rotate_v2" in value
    assert "roster-head-witness-rotation-source-auth-failed" in value
    assert (
        "decision_trace_trust_state_witness_quorum_policy_"
        "monotonic_head_witness_key_rotation"
        in value
    )


def test_layer211_rotation_preserves_exact_roster_head_truth():
    value = rotation_sql()

    for field in (
        "v_current.sequence",
        "v_current.head_sha256",
        "v_current.generation",
        "v_current.policy_sha256",
        "v_current.state_sha256",
    ):
        assert field in value

    # State mutation is limited to the witness authentication material.
    rotation = value.split(
        "create or replace function "
        "foundation.project_l_roster_head_witness_rotate_v2",
        1,
    )[1]
    update_block = rotation.split(
        "update foundation.project_l_roster_head_witness_state",
        1,
    )[1].split("if not found", 1)[0]
    set_clause = update_block.split("where", 1)[0]
    assert "auth_key_id=p_target_auth_key_id" in set_clause
    assert "auth_tag=v_target_tag" in set_clause
    assert "head_sha256=" not in set_clause
    assert "generation=" not in set_clause
    assert "policy_sha256=" not in set_clause
    assert "state_sha256=" not in set_clause

    # The CAS WHERE clause must bind the unchanged roster truth.
    where_clause = update_block.split("where", 1)[1]
    assert "head_sha256=v_current.head_sha256" in where_clause
    assert "generation=v_current.generation" in where_clause
    assert "policy_sha256=v_current.policy_sha256" in where_clause
    assert "state_sha256=v_current.state_sha256" in where_clause


def test_layer211_rotation_rpc_is_gateway_only():
    value = " ".join(rotation_sql().split())

    assert (
        "revoke all on function "
        "foundation.project_l_roster_head_witness_rotate_v2"
        in value
    )
    assert (
        "grant execute on function "
        "foundation.project_l_roster_head_witness_rotate_v2(text,text,text) "
        "to foundation_gateway"
        in value
    )


def test_layer211_edge_exposes_bounded_rotation_without_secrets():
    value = edge()

    assert "external-roster-head-rotate" in value
    assert "project_l_roster_head_witness_rotate_v2" in value
    assert "targetauthkeyid" in value
    assert "decrypted_secret" not in value
