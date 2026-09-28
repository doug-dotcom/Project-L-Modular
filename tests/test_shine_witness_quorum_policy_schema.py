from pathlib import Path


MIGRATION = Path(
    "supabase/migrations/"
    "20260928093500_project_l_layer197_witness_quorum_policy.sql"
)


def source() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_quorum_policy_tables_are_service_role_read_only():
    sql = source()

    assert "shine_ai_witness_quorum_policy_state" in sql
    assert "shine_ai_witness_quorum_policy_ledger" in sql
    assert "enable row level security" in sql
    assert "revoke all on public.shine_ai_witness_quorum_policy_state" in sql
    assert "revoke all on public.shine_ai_witness_quorum_policy_ledger" in sql
    assert "grant select on public.shine_ai_witness_quorum_policy_state" in sql
    assert "grant select on public.shine_ai_witness_quorum_policy_ledger" in sql


def test_genesis_policy_is_hard_pinned_in_database_boundary():
    sql = source()

    assert "foundation-project-l" in sql
    assert "project-l-redis" in sql
    assert "'aac7d1acaec5bf64d5f7d3fe535cbb48e99df0900eb91e8a8b44cbbfcbb5a92e'" in sql
    assert "minimumwitnesses" in sql
    assert "'generation',1" in sql


def test_snapshot_cross_checks_state_against_append_only_ledger():
    sql = source()

    assert "witness-quorum-policy-cardinality-mismatch" in sql
    assert "witness-quorum-policy-high-water-mismatch" in sql
    assert "v_state.generation <> v_ledger.generation" in sql
    assert "v_state.policy_sha256 <> v_ledger.policy_sha256" in sql


def test_layer197_exposes_no_policy_advance_rpc():
    sql = source()

    assert "shine_ai_witness_quorum_policy_bootstrap_v1" in sql
    assert "shine_ai_witness_quorum_policy_snapshot_v1" in sql
    assert "shine_ai_witness_quorum_policy_advance" not in sql
    assert "signed-transition" not in sql


def test_layer197_policy_contains_no_secret_material():
    sql = source()

    for token in (
        "private_key",
        "app_secret",
        "storage_auth_tag",
        "hmac_secret",
        "redis_url",
    ):
        assert token not in sql
