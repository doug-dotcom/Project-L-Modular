from pathlib import Path


MIGRATION = Path(
    "supabase/migrations/"
    "20260928110100_project_l_layer204_external_witness_roster.sql"
)


def source() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_layer204_roster_tables_are_service_role_read_only():
    sql = source()

    assert "shine_ai_external_witness_roster_state" in sql
    assert "shine_ai_external_witness_roster_ledger" in sql
    assert "enable row level security" in sql
    assert (
        "revoke all on public.shine_ai_external_witness_roster_state"
        in sql
    )
    assert (
        "revoke all on public.shine_ai_external_witness_roster_ledger"
        in sql
    )
    assert (
        "grant select on public.shine_ai_external_witness_roster_state "
        "to service_role"
    ) in sql
    assert (
        "grant select on public.shine_ai_external_witness_roster_ledger "
        "to service_role"
    ) in sql


def test_layer204_bootstrap_is_exact_certified_genesis():
    sql = source()
    bootstrap = sql.split(
        "create or replace function "
        "public.shine_ai_external_witness_roster_bootstrap_v1",
        1,
    )[1]

    assert "foundation-project-l" in bootstrap
    assert "redis-project-l" in bootstrap
    assert (
        "a5c456d49e47f1be3f2a7b7ed017328"
        "844484ba05c4e6ef3212412c6361156c4"
        in bootstrap
    )
    assert "'genesis-pin'" in bootstrap


def test_layer204_exposes_no_membership_advance_rpc():
    sql = source()

    assert "external_witness_roster_advance" not in sql
    assert "external_witness_roster_transition" not in sql


def test_layer204_snapshot_cross_checks_state_and_ledger():
    sql = source()

    assert "external-witness-roster-high-water-mismatch" in sql
    assert "v_state.generation <> v_ledger.generation" in sql
    assert "v_state.accepted_witness_ids <> v_ledger.accepted_witness_ids" in sql
    assert "v_state.policy_sha256 <> v_ledger.policy_sha256" in sql
    assert "v_state.state_sha256 <> v_ledger.state_sha256" in sql


def test_layer204_schema_stores_hmac_tag_not_secret():
    sql = source()

    assert "storage_auth_tag" in sql
    for token in (
        "storage_secret",
        "private_key",
        "redis_url",
        "app_secret",
    ):
        assert token not in sql
