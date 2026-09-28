from pathlib import Path


MIGRATION = Path(
    "supabase/migrations/"
    "20260928214500_project_l_layer206_external_witness_roster_stable_high_water.sql"
)


def source() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def high_water_condition(sql: str) -> str:
    start = sql.index("if v_state.generation")
    end = sql.index("then", start)
    return sql[start:end]


def test_roster_high_water_binds_stable_trust_identity():
    sql = source()
    condition = high_water_condition(sql)

    for field in (
        "v_state.generation <> v_ledger.generation",
        "v_state.minimum_witnesses <> v_ledger.minimum_witnesses",
        "v_state.accepted_witness_ids <> v_ledger.accepted_witness_ids",
        "v_state.previous_policy_sha256",
        "v_state.policy_sha256 <> v_ledger.policy_sha256",
        "v_state.state_sha256 <> v_ledger.state_sha256",
    ):
        assert field in condition


def test_roster_high_water_excludes_local_storage_auth_metadata():
    sql = source()
    condition = high_water_condition(sql)

    assert "storage_auth_key_id" not in condition
    assert "storage_auth_tag" not in condition

    # Current authentication metadata is still returned so the caller can
    # verify the HMAC envelope independently.
    assert "'storage_auth_key_id',v_state.storage_auth_key_id" in sql
    assert "'storage_auth_tag',v_state.storage_auth_tag" in sql


def test_roster_high_water_still_fails_closed_on_trust_drift():
    sql = source()

    assert "external-witness-roster-high-water-mismatch" in sql
    assert "external-witness-roster-cardinality-mismatch" in sql
    assert "order by generation desc, id desc" in sql
