from pathlib import Path

MIGRATION = Path(
    "supabase/migrations/20260929165000_project_l_memory_layer302_counterfactual_shadow_quality.sql"
)
EDGE = Path("supabase/functions/l-companion/index.ts")


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def _edge() -> str:
    return EDGE.read_text(encoding="utf-8")


def test_layer302_requires_repeatable_counterfactual_quality():
    sql = _sql()

    for marker in (
        "v_comparisons>=10",
        "v_distinct_days>=3",
        "v_distinct_queries>=6",
        "v_distinct_cohorts>=4",
        "v_win_rate>=0.70",
        "coalesce(v_advantage_avg,0)>=0.08",
        "coalesce(v_proposed_avg,0)>=0.65",
        "v_material_loss_share<=0.20",
    ):
        assert marker in sql

    assert "activation_requires_counterfactual_shadow_quality" in sql


def test_layer302_scoring_matches_layer296_proxy():
    sql = _sql()

    assert "project_l_retrieval_proxy_score_v1" in sql
    assert "intentionally identical to layer 296 deterministic_retrieval_proxy_v1" in sql
    for term in ("0.25", "0.35", "0.20", "0.10", "0.05", "0.95"):
        assert term in sql


def test_layer302_counterfactual_evidence_is_generation_bound_append_only_and_content_free():
    sql = _sql()

    assert "project_l_adaptive_memory_shadow_counterfactuals" in sql
    assert "activation_generation bigint not null" in sql
    assert "query_fingerprint" in sql
    assert "query_cohort_fingerprint" in sql
    assert "query_text" not in sql
    assert "grant select, insert on table public.project_l_adaptive_memory_shadow_counterfactuals" in sql
    assert "grant update" not in sql
    assert "grant delete" not in sql


def test_layer302_activation_requires_both_burn_in_and_counterfactual_certificates():
    sql = _sql()

    assert "and v_shadow_certified" in sql
    assert "and v_counter_certified" in sql
    assert "configured_active_but_counterfactual_uncertified" in sql
    assert "'requiredlayerfloor',302" in sql.replace(" ", "")


def test_layer302_companion_executes_unused_shadow_alternative():
    edge = _edge()

    assert "runShadowCounterfactualRetrieval" in edge
    assert "shadowCounterfactualMemory" in edge
    assert "shadowCounterfactualData" in edge
    assert "counterfactualRetrievalMetrics" in edge
    assert "shadowCounterfactualInfluencedResponse=false" in edge
    assert '"project_l_record_adaptive_shadow_counterfactual_v1"' in edge


def test_layer302_companion_only_compares_mode_changing_automatic_shadow_requests():
    edge = _edge()

    assert "shadowCounterfactualEligible" in edge
    assert "explicitRetrievalModeRaw.length===0" in edge
    assert "adaptiveMemoryActivation.effectiveMode===\"shadow_only\"" in edge
    assert "proposedCounterfactualMode!==selectedRetrievalMode" in edge


def test_layer302_companion_sends_content_free_quality_metrics_only():
    edge = _edge()

    assert "counterfactualRetrievalMetrics" in edge
    assert "p_actual_metrics:counterfactualRetrievalMetrics(" in edge
    assert "memoryData," in edge
    assert "p_proposed_metrics:counterfactualRetrievalMetrics(" in edge
    assert "shadowCounterfactualData," in edge
    assert "p_query_fingerprint:servedQueryFingerprint" in edge
    assert "p_query_cohort_fingerprint:servedQueryCohortFingerprint" in edge
