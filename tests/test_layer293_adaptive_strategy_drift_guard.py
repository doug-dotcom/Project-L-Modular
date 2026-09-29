from pathlib import Path

MIGRATION = Path(
    "supabase/migrations/20260929112200_project_l_layer293_adaptive_strategy_drift_guard.sql"
)


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def test_layer293_migration_exists_and_is_bounded():
    sql = _sql()

    assert "project_l_adaptive_strategy_drift_guard_v1" in sql
    assert "minimumsupportingservedoutcomes',5" in sql.replace(" ", "")
    assert "minimumdistinctdays',3" in sql.replace(" ", "")
    assert "minimumspanhours',48" in sql.replace(" ", "")
    assert "maximumevidenceagedays',14" in sql.replace(" ", "")
    assert "maximumlast24hburstshare',0.60" in sql.replace(" ", "")
    assert "modeswitchcooldownhours',72" in sql.replace(" ", "")
    assert "oscillationwindowdays',7" in sql.replace(" ", "")
    assert "minimumadvantage',0.08" in sql.replace(" ", "")


def test_layer293_uses_served_evidence_and_blocks_drift_patterns():
    sql = _sql()

    assert "and served_at <= p_now" in sql
    assert "where served" in sql
    assert "insufficient_served_support" in sql
    assert "insufficient_distinct_days" in sql
    assert "insufficient_evidence_span" in sql
    assert "stale_evidence" in sql
    assert "last_24h_burst_dominance" in sql
    assert "mode_switch_cooldown" in sql
    assert "mode_oscillation" in sql
    assert "insufficient_advantage" in sql


def test_layer293_event_ledger_is_idempotent_and_serialised():
    sql = _sql()

    assert "project_l_retrieval_adaptation_events" in sql
    assert "pg_advisory_xact_lock" in sql
    assert "duplicateSuppressed".lower() in sql
    assert "already_preferred" in sql


def test_layer293_surface_is_service_role_only_and_invoker_safe():
    sql = _sql()

    assert "security invoker" in sql
    assert "enable row level security" in sql
    assert "revoke all on table public.project_l_retrieval_adaptation_events" in sql
    assert "from public, anon, authenticated" in sql
    assert "grant select, insert on table public.project_l_retrieval_adaptation_events" in sql
    assert "to service_role" in sql
    assert "revoke all on function public.project_l_adaptive_strategy_drift_guard_v1" in sql
    assert "grant execute on function public.project_l_adaptive_strategy_drift_guard_v1" in sql
