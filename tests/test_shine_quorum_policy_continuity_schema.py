from pathlib import Path


MIGRATION = Path(
    "supabase/migrations/"
    "20260928103200_project_l_layer202_quorum_policy_continuity.sql"
)


def source() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_layer202_expands_policy_state_only_to_previous_quorum_transition():
    sql = source()

    assert "source in ('genesis-pin','previous-quorum-transition')" in sql
    assert (
        "acceptance_mode in ('genesis-pin','previous-quorum-transition')"
        in sql
    )
    assert "authorizing_witness_ids text[]" in sql
    assert "authorization_sha256 text" in sql


def test_layer202_snapshot_checks_full_append_only_policy_chain():
    sql = source()

    assert "shine_ai_witness_quorum_policy_snapshot_v2" in sql
    assert "v_ledger_count<>v_state.generation" in sql
    assert "lag(policy_sha256) over(order by generation)" in sql
    assert "generation<>prior_generation+1" in sql
    assert "previous_policy_sha256 is distinct from prior_sha" in sql
    assert "witness-quorum-policy-history-chain-mismatch" in sql
    assert "witness-quorum-policy-high-water-mismatch" in sql


def test_layer202_advance_is_exact_one_step_and_predecessor_bound():
    sql = source()
    advance = sql.split(
        "create or replace function public."
        "shine_ai_witness_quorum_policy_advance_v2"
    )[1]

    assert "p_next_generation<>p_expected_generation+1" in advance
    assert (
        "p_next_previous_policy_sha256<>p_expected_policy_sha256"
        in advance
    )
    assert "witness quorum policy transition precondition mismatch" in advance
    assert "witness quorum policy no-op transition" in advance
    assert "pg_advisory_xact_lock" in advance


def test_layer202_database_requires_previous_policy_quorum_identity():
    sql = source()
    advance = sql.split(
        "create or replace function public."
        "shine_ai_witness_quorum_policy_advance_v2"
    )[1]

    assert "v_current_minimum" in advance
    assert "cardinality(p_authorizing_witness_ids)<v_current_minimum" in advance
    assert "count(distinct x)" in advance
    assert "not (x=any(v_current_ids))" in advance
    assert "authorization from non-member witness" in advance


def test_layer202_policy_tables_remain_service_role_read_only():
    sql = source()

    assert "grant insert on public.shine_ai_witness_quorum_policy_state" not in sql
    assert "grant update on public.shine_ai_witness_quorum_policy_state" not in sql
    assert "grant insert on public.shine_ai_witness_quorum_policy_ledger" not in sql
    assert "grant update on public.shine_ai_witness_quorum_policy_ledger" not in sql
    assert (
        "grant execute on function public."
        "shine_ai_witness_quorum_policy_advance_v2"
        in sql
    )


def test_layer202_persists_only_authorization_metadata_not_hmac_tags():
    sql = source()

    assert "authorizing_witness_ids" in sql
    assert "authorization_sha256" in sql
    for token in (
        "authorization_auth_tag",
        "witness_secret",
        "private_key",
        "redis_url",
        "client_token",
    ):
        assert token not in sql
