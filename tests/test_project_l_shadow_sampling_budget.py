from pathlib import Path

MIGRATION = Path(
    "supabase/migrations/20260929183000_project_l_memory_layer303_shadow_sampling_budget.sql"
)
EDGE = Path("supabase/functions/l-companion/index.ts")


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def _edge() -> str:
    return EDGE.read_text(encoding="utf-8")


def test_layer303_has_hard_daily_cohort_and_generation_budgets():
    sql = _sql()

    assert "v_daily>=4" in sql
    assert "v_cohort_daily>=1" in sql
    assert "v_generation_total>=28" in sql
    assert "dailylimit',4" in sql.replace(" ", "")
    assert "cohortdailylimit',1" in sql.replace(" ", "")
    assert "generationlimit',28" in sql.replace(" ", "")


def test_layer303_stops_sampling_after_quality_certification():
    sql = _sql()

    assert "quality_already_certified" in sql
    assert "project_l_adaptive_counterfactual_certification_v1" in sql
    assert "not v_quality_certified" in sql


def test_layer303_reservation_is_append_only_and_retry_safe():
    sql = _sql()

    assert "project_l_adaptive_memory_counterfactual_sampling" in sql
    assert "unique(user_id,request_id)" in sql
    assert "project_l_layer303_sampling_replay_mismatch" in sql
    assert "reservationconsumesbudget',v_admitted" in sql.replace(" ", "")
    assert "grant select, insert on table public.project_l_adaptive_memory_counterfactual_sampling" in sql
    assert "grant update" not in sql
    assert "grant delete" not in sql


def test_layer303_stack_health_and_activation_floor_include_sampling_controls():
    sql = _sql()

    assert "layer303_sample_admission" in sql
    assert "layer303_sampling_status" in sql
    assert "counterfactual_sampling_table_rls" in sql
    assert "'requiredlayerfloor',303" in sql.replace(" ", "")
    assert "required_layer_floor=303" in sql


def test_layer303_companion_asks_for_admission_before_counterfactual_execution():
    edge = _edge()

    admission = edge.index('"project_l_adaptive_counterfactual_sample_admission_v1"')
    execution = edge.index("shadowCounterfactualMemory=await runShadowCounterfactualRetrieval")
    assert admission < execution
    assert "shadowCounterfactualAdmitted" in edge
    assert "adaptiveShadowCounterfactualSampling" in edge


def test_layer303_companion_executes_alternative_only_when_admitted():
    edge = _edge()

    assert "if(shadowCounterfactualEligible){" in edge
    assert "if(shadowCounterfactualAdmitted){" in edge
    assert "p_query_cohort_fingerprint:servedQueryCohortFingerprint" in edge
    assert "p_explicit_mode_used:false" in edge


def test_layer303_sampling_telemetry_is_exposed_without_answer_influence():
    edge = _edge()

    assert "adaptive_shadow_counterfactual_admitted" in edge
    assert "adaptive_shadow_counterfactual_sampling_reason" in edge
    assert "shadowCounterfactualInfluencedResponse=false" in edge
