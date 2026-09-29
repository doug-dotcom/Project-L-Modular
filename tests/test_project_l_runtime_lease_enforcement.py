from pathlib import Path

MIGRATION = Path(
    "supabase/migrations/20260929122000_project_l_layer295_runtime_lease_enforcement.sql"
)
EDGE = Path("supabase/functions/l-companion/index.ts")


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def _edge() -> str:
    return EDGE.read_text(encoding="utf-8")


def test_layer295_selector_is_read_only_and_service_role_only():
    sql = _sql()

    assert "project_l_runtime_retrieval_decision_v1" in sql
    assert "stable" in sql
    assert "security invoker" in sql
    assert "insert into public.project_l_retrieval" not in sql
    assert "update public.project_l_retrieval" not in sql
    assert "from public, anon, authenticated" in sql
    assert "to service_role" in sql


def test_layer295_priority_is_explicit_then_lease_then_default():
    sql = _sql()

    explicit_pos = sql.index("if v_explicit is not null then")
    lease_pos = sql.index("from public.project_l_retrieval_strategy_leases")
    default_return_pos = sql.index("'status','default'")

    assert explicit_pos < lease_pos
    assert lease_pos < default_return_pos
    assert "lease_clock_expired_base" in sql
    assert "desired_mode_unavailable_fallback_base" in sql


def test_layer295_hybrid_is_not_assumed_runtime_ready():
    sql = _sql()

    assert "p_hybrid_ready boolean default false" in sql
    assert "v_desired = 'hybrid' and coalesce(p_hybrid_ready,false)" in sql


def test_layer295_live_companion_calls_runtime_selector():
    edge = _edge()

    assert 'db.rpc("project_l_runtime_retrieval_decision_v1"' in edge
    assert "selectedRetrievalMode" in edge
    assert 'selectedRetrievalMode==="semantic"' in edge
    assert "runtimeRetrievalDecision" in edge
    assert "retrievalIntent" in edge
    assert "explicitRetrievalModeRaw" in edge


def test_layer295_companion_fails_open_to_existing_default_if_selector_unavailable():
    edge = _edge()

    assert "runtime_retrieval_decision_unavailable" in edge
    assert 'semanticGate.productionSemanticEnabled===true?"semantic":"lexical"' in edge


def test_layer295_companion_reports_strategy_decision_in_response_and_telemetry():
    edge = _edge()

    assert "runtime_strategy_source" in edge
    assert "runtime_strategy_effective_mode" in edge
    assert "runtime_strategy_reason" in edge
    assert "runtimeRetrievalDecision," in edge
