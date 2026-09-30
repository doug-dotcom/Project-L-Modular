from pathlib import Path

MIGRATION = Path(
    "supabase/migrations/20260929114500_project_l_layer294_strategy_lease_renewal.sql"
)


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_layer294_creates_time_bounded_learned_strategy_leases():
    sql = _sql()

    assert "project_l_retrieval_strategy_leases" in sql
    assert "project_l_retrieval_strategy_lease_events" in sql
    assert "project_l_strategy_lease_status_v1" in sql
    assert "interval '7 days'" in sql
    assert "state in ('active','expired','revoked')" in sql


def test_layer294_renews_only_from_fresh_distributed_served_evidence():
    sql = _sql()

    assert "where served" in sql
    assert "mode = v_lease.learned_mode" in sql
    assert "v_count >= 5" in sql
    assert "v_days >= 3" in sql
    assert "v_span_hours >= 48" in sql
    assert "p_now - interval '72 hours'" in sql
    assert "renewed_fresh_served_evidence" in sql


def test_layer294_has_quality_decay_and_expiry_fallback():
    sql = _sql()

    assert "originalbaseaveragescore" in sql
    assert "originallearnedaveragescore" in sql
    assert "minimum margin" not in sql  # prose labels stay machine-readable below
    assert "minimummarginaboveoriginalbase" in sql.replace(" ", "")
    assert "maximumdropfromoriginallearned" in sql.replace(" ", "")
    assert "revoked_quality_decay" in sql
    assert "expired_insufficient_fresh_evidence" in sql
    assert "v_effective_mode := v_lease.base_mode" in sql


def test_layer294_terminal_states_cannot_self_revive():
    sql = _sql()

    assert "terminal lease states do not auto-revive" in sql
    assert "terminal_lease_requires_new_layer293_transition" in sql
    assert "if v_lease.state in ('expired','revoked')" in sql


def test_layer294_surface_is_service_role_only_and_invoker_safe():
    sql = _sql()

    assert "security invoker" in sql
    assert sql.count("enable row level security") >= 2
    assert "revoke all on table public.project_l_retrieval_strategy_leases" in sql
    assert "revoke all on table public.project_l_retrieval_strategy_lease_events" in sql
    assert "from public, anon, authenticated" in sql
    assert "to service_role" in sql
    assert "revoke all on function public.project_l_strategy_lease_status_v1" in sql
