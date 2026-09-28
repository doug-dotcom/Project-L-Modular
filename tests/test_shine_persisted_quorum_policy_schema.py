from pathlib import Path


MIGRATION = Path(
    "supabase/migrations/"
    "20260928095000_project_l_layer199_persisted_quorum_policy.sql"
)


def source() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_layer199_policy_store_is_service_role_read_only():
    sql = source()

    assert "shine_ai_witness_quorum_policy_state" in sql
    assert "shine_ai_witness_quorum_policy_ledger" in sql
    assert "enable row level security" in sql
    assert (
        "revoke all on public.shine_ai_witness_quorum_policy_state"
        in sql
    )
    assert (
        "revoke all on public.shine_ai_witness_quorum_policy_ledger"
        in sql
    )
    assert (
        "grant select on public.shine_ai_witness_quorum_policy_state"
        in sql
    )
    assert (
        "grant select on public.shine_ai_witness_quorum_policy_ledger"
        in sql
    )


def test_layer199_genesis_policy_matches_layer198_two_of_two_contract():
    sql = source()

    assert "array['foundation-project-l','redis-project-l']" in sql
    assert (
        "26b6d1a3b4183cfa596f8c9c06c18e73"
        "aa0eda6a80a6362649130e9357bf220e"
        in sql
    )
    assert "'minimumwitnesses',2" in sql
    assert "'generation',1" in sql
    assert "'previouspolicysha256',null" in sql


def test_layer199_snapshot_cross_checks_append_only_policy_high_water():
    sql = source()

    assert "witness-quorum-policy-cardinality-mismatch" in sql
    assert "witness-quorum-policy-high-water-mismatch" in sql
    assert "v_state.generation <> v_ledger.generation" in sql
    assert "v_state.minimum_witnesses <> v_ledger.minimum_witnesses" in sql
    assert (
        "v_state.accepted_witness_ids <> v_ledger.accepted_witness_ids"
        in sql
    )
    assert "v_state.policy_sha256 <> v_ledger.policy_sha256" in sql


def test_layer199_has_no_policy_transition_or_generic_write_path():
    sql = source()

    assert "shine_ai_witness_quorum_policy_bootstrap_v1" in sql
    assert "shine_ai_witness_quorum_policy_snapshot_v1" in sql
    assert "shine_ai_witness_quorum_policy_advance" not in sql
    assert "signed-transition" not in sql
    assert "grant insert" not in sql
    assert "grant update" not in sql


def test_layer199_policy_store_contains_no_witness_or_storage_secrets():
    sql = source()

    for token in (
        "private_key",
        "app_secret",
        "auth_tag",
        "hmac_secret",
        "redis_url",
        "client_token",
    ):
        assert token not in sql
