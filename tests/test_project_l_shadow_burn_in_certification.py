from pathlib import Path

MIGRATION = Path(
    "supabase/migrations/20260929154000_project_l_memory_layer301_shadow_burn_in.sql"
)
EDGE = Path("supabase/functions/l-companion/index.ts")


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def _edge() -> str:
    return EDGE.read_text(encoding="utf-8")


def test_layer301_requires_substantial_current_generation_shadow_burn_in():
    sql = _sql()

    for marker in (
        "v_burn_in_hours >= 72",
        "v_observation_count >= 20",
        "v_distinct_days >= 3",
        "v_distinct_exact_queries >= 8",
        "v_distinct_cohorts >= 5",
        "v_mode_change_count >= 5",
        "v_mode_change_cohorts >= 3",
    ):
        assert marker in sql

    assert "activation_requires_shadow_burn_in" in sql


def test_layer301_binds_shadow_evidence_to_activation_generation():
    sql = _sql()

    assert "activation_generation bigint not null" in sql
    assert "where activation_generation=v_generation" in sql
    assert "activation_basis_shadow_generation" in sql
    assert "shadow_started_at" in sql


def test_layer301_shadow_observations_are_append_only_and_content_free():
    sql = _sql()

    assert "project_l_adaptive_memory_shadow_observations" in sql
    assert "query_fingerprint" in sql
    assert "query_cohort_fingerprint" in sql
    assert "query_text" not in sql
    assert "grant select, insert on table public.project_l_adaptive_memory_shadow_observations" in sql
    assert "grant update" not in sql
    assert "grant delete" not in sql


def test_layer301_replay_mismatch_and_explicit_requests_fail_closed():
    sql = _sql()

    assert "project_l_layer301_shadow_replay_mismatch" in sql
    assert "explicit_request_not_shadow_burn_in" in sql
    assert "not_eligible_shadow_state" in sql


def test_layer301_activation_status_requires_stack_and_shadow_certificate():
    sql = _sql()

    assert "and v_shadow_certified" in sql
    assert "configured_active_but_shadow_uncertified" in sql
    assert "'shadowcertification',v_shadow_cert" in sql.replace(" ", "")
    assert "'requiredlayerfloor',301" in sql.replace(" ", "")


def test_layer301_companion_records_shadow_observations_with_keyed_fingerprints():
    edge = _edge()

    assert '"project_l_record_adaptive_shadow_observation_v1"' in edge
    assert "adaptiveShadowObservation" in edge
    assert "p_query_fingerprint:servedQueryFingerprint" in edge
    assert "p_query_cohort_fingerprint:servedQueryCohortFingerprint" in edge
    assert "p_actual_mode:selectedRetrievalMode" in edge
    assert "shadowProposedRetrievalDecision" in edge


def test_layer301_companion_never_counts_explicit_requests_as_burn_in():
    edge = _edge()

    assert "p_explicit_mode_used:explicitRetrievalModeRaw.length>0" in edge
    assert "adaptiveMemoryActivation.effectiveMode" in edge
