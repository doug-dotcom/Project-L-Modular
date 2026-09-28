from pathlib import Path


MIGRATION = Path(
    "supabase/migrations/"
    "20260928104500_project_l_layer203_quorum_policy_continuity.sql"
)


def source() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_layer203_expands_policy_authority_only_to_previous_quorum_transition():
    sql = source()

    assert "source in ('genesis-pin','previous-quorum-transition')" in sql
    assert (
        "acceptance_mode in ('genesis-pin','previous-quorum-transition')"
        in sql
    )
    assert "authorizing_witness_ids text[]" in sql
    assert "authorization_sha256 text" in sql


def test_layer203_snapshot_verifies_history_chain_and_authenticated_high_water():
    sql = source()

    assert "shine_ai_witness_quorum_policy_snapshot_v3" in sql
    assert "v_ledger_count<>v_state.generation" in sql
    assert "lag(policy_sha256) over(order by generation)" in sql
    assert "generation<>prior_generation+1" in sql
    assert "previous_policy_sha256 is distinct from prior_sha" in sql
    assert "witness-quorum-policy-history-chain-mismatch" in sql
    assert "witness-quorum-policy-high-water-mismatch" in sql
    assert "'state_sha256',v_state.state_sha256" in sql
    assert "'storage_auth_key_id',v_state.storage_auth_key_id" in sql
    assert "'storage_auth_tag',v_state.storage_auth_tag" in sql


def test_layer203_advance_is_one_step_predecessor_bound_and_non_noop():
    sql = source()
    advance = sql.split(
        "create or replace function public."
        "shine_ai_witness_quorum_policy_advance_v3"
    )[1]

    assert "p_next_generation<>p_expected_generation+1" in advance
    assert (
        "p_next_previous_policy_sha256<>p_expected_policy_sha256"
        in advance
    )
    assert "witness quorum policy transition precondition mismatch" in advance
    assert "witness quorum policy no-op transition" in advance
    assert "pg_advisory_xact_lock" in advance


def test_layer203_database_requires_previous_policy_quorum_members():
    sql = source()
    advance = sql.split(
        "create or replace function public."
        "shine_ai_witness_quorum_policy_advance_v3"
    )[1]

    assert "v_current_minimum" in advance
    assert "cardinality(p_authorizing_witness_ids)<v_current_minimum" in advance
    assert "count(distinct x)" in advance
    assert "not (x=any(v_current_ids))" in advance
    assert "authorization from non-member witness" in advance


def test_layer203_advance_commits_new_authenticated_policy_state_atomically():
    sql = source()
    advance = sql.split(
        "create or replace function public."
        "shine_ai_witness_quorum_policy_advance_v3"
    )[1]

    assert "state_sha256=p_state_sha256" in advance
    assert "storage_auth_key_id=p_storage_auth_key_id" in advance
    assert "storage_auth_tag=p_storage_auth_tag" in advance
    assert "acceptance_mode" in advance
    assert "'previous-quorum-transition'" in advance


def test_layer203_policy_tables_remain_service_role_read_only():
    sql = source()

    assert "grant insert on public.shine_ai_witness_quorum_policy_state" not in sql
    assert "grant update on public.shine_ai_witness_quorum_policy_state" not in sql
    assert "grant insert on public.shine_ai_witness_quorum_policy_ledger" not in sql
    assert "grant update on public.shine_ai_witness_quorum_policy_ledger" not in sql
    assert (
        "grant execute on function public."
        "shine_ai_witness_quorum_policy_advance_v3"
        in sql
    )


def test_layer203_ledger_keeps_only_authorisation_digest_not_raw_tags():
    sql = source()

    assert "authorizing_witness_ids" in sql
    assert "authorization_sha256" in sql
    assert "authorization_auth_tag" not in sql
    assert "witness_secret" not in sql
    assert "private_key" not in sql
    assert "redis_url" not in sql
    assert "client_token" not in sql
