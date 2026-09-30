from pathlib import Path

MIGRATION = Path(
    "supabase/migrations/20260929130000_project_l_layer296_served_outcome_renewal_feed.sql"
)
EDGE = Path("supabase/functions/l-companion/index.ts")


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def _edge() -> str:
    return EDGE.read_text(encoding="utf-8")


def test_layer296_creates_append_only_content_free_outcome_ledger():
    sql = _sql()

    assert "project_l_retrieval_served_outcomes" in sql
    assert "raw memory content is never written" in sql
    assert "grant select, insert on table public.project_l_retrieval_served_outcomes" in sql
    assert "grant update" not in sql
    assert "grant delete" not in sql
    assert "enable row level security" in sql


def test_layer296_proxy_evidence_cannot_promote_new_strategy():
    sql = _sql()

    assert "adaptation_eligible boolean not null default false" in sql
    assert "'adaptationeligible',false" in sql.replace(" ", "")
    assert "runtime telemetry may renew/revoke" in sql
    assert "is not eligible to promote a new strategy" in sql.lower()


def test_layer296_renewal_requires_genuine_active_lease_service():
    sql = _sql()

    assert "v_lease_applied" in sql
    assert "v_source = 'active_lease'" in sql
    assert "not v_explicit" in sql
    assert "not v_retrieval_fallback" in sql
    assert "v_returned > 0" in sql


def test_layer296_has_idempotent_bounded_scoring_and_feed():
    sql = _sql()

    assert "unique(user_id, request_id)" in sql
    assert "on conflict (user_id,request_id) do nothing" in sql
    assert "deterministic_retrieval_proxy_v1" in sql
    assert "project_l_served_outcome_feed_v1" in sql
    assert "project_l_auto_renewal_feed_v1" in sql
    assert "least(0.95,greatest(0.05,v_score))" in sql


def test_layer296_live_companion_records_and_feeds_outcomes():
    edge = _edge()

    assert '"project_l_record_served_outcome_v1"' in edge
    assert (
        '"project_l_auto_renewal_feed_v1"' in edge
        or '"project_l_governed_lease_evaluation_v1"' in edge
    )
    assert "servedOutcome" in edge
    assert "strategyLeaseEvaluation" in edge
    assert "retrievalLearning" in edge


def test_layer296_edge_passes_governed_runtime_signals_not_memory_content():
    edge = _edge()

    assert "returned_count:matches.length" in edge
    assert "safe_assertion_count:reconciliationSummary.safeForFactualAssertion" in edge
    assert "lease_applied:runtimeRetrievalDecision.leaseApplied===true" in edge
    assert "explicit_mode_used:explicitRetrievalModeRaw.length>0" in edge
    assert "p_payload:{" in edge
