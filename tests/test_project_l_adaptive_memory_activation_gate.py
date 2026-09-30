from pathlib import Path

MIGRATION = Path(
    "supabase/migrations/20260929150000_project_l_memory_layer300_adaptive_activation_gate.sql"
)
EDGE = Path("supabase/functions/l-companion/index.ts")


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def _edge() -> str:
    return EDGE.read_text(encoding="utf-8")


def test_layer300_defaults_to_shadow_only_with_audited_generation_control():
    sql = _sql()

    assert "project_l_adaptive_memory_activation" in sql
    assert "mode text not null default 'shadow_only'" in sql
    assert "generation bigint not null default 1" in sql
    assert "project_l_adaptive_memory_activation_events" in sql
    assert "stale_expected_generation" in sql
    assert "activation_requires_shadow_only_prestate" in sql


def test_layer300_health_certificate_covers_layers_293_through_299_and_rls():
    sql = _sql()

    for marker in (
        "layer293_guard",
        "layer294_lease_evaluator",
        "layer295_runtime_selector",
        "layer296_outcome_recorder",
        "layer297_governed_evaluator",
        "layer298_exact_binding",
        "layer299_cohort_recorder",
        "layer299_cohort_feed",
        "adaptation_table_rls",
        "lease_table_rls",
        "outcome_table_rls",
        "query_binding_table_rls",
        "cohort_binding_table_rls",
    ):
        assert marker in sql

    assert "'stackready',v_stack_ready" in sql.replace(" ", "")


def test_layer300_active_requires_healthy_stack_and_fails_closed_after_degradation():
    sql = _sql()

    assert "activation_requires_healthy_stack" in sql
    assert "v_runtime_enabled :=" in sql
    assert "v_cfg.mode='active'" in sql
    assert "and v_stack_ready" in sql
    assert "configured_active_but_stack_unhealthy" in sql


def test_layer300_surfaces_are_service_role_only_and_invoker_safe():
    sql = _sql()

    assert sql.count("security invoker") >= 3
    assert "from public, anon, authenticated" in sql
    assert "to service_role" in sql
    assert sql.count("enable row level security") >= 2


def test_layer300_companion_checks_master_gate_before_adaptive_runtime_influence():
    edge = _edge()

    assert '"project_l_adaptive_memory_activation_status_v1"' in edge
    assert "adaptiveMemoryActivation" in edge
    assert "adaptiveRuntimeInfluenceEnabled" in edge
    assert "shadowProposedRetrievalDecision" in edge
    assert "adaptive_activation_gate_shadow_only" in edge


def test_layer300_explicit_mode_remains_outside_adaptive_kill_switch():
    edge = _edge()

    assert "explicitRetrievalModeRaw.length>0" in edge
    assert "adaptiveRuntimeInfluenceEnabled" in edge
    assert "explicit_request_preserved_by_activation_gate" in edge


def test_layer300_missing_gate_fails_closed_to_shadow_only():
    edge = _edge()

    assert "activation_gate_unavailable" in edge
    assert "runtimeInfluenceEnabled:false" in edge
    assert "effectiveMode:\"shadow_only\"" in edge
