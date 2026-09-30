from pathlib import Path

MIGRATION = Path(
    "supabase/migrations/20260929140000_project_l_layer298_evidence_independence_guard.sql"
)
EDGE = Path("supabase/functions/l-companion/index.ts")


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def _edge() -> str:
    return EDGE.read_text(encoding="utf-8")


def test_layer298_stores_only_privacy_safe_query_fingerprints():
    sql = _sql()

    assert "project_l_retrieval_outcome_query_bindings" in sql
    assert "query_fingerprint ~ '^[0-9a-f]{64}$'" in sql
    assert "raw query text is never stored" in sql
    assert "query_text" not in sql
    assert "grant select, insert on table public.project_l_retrieval_outcome_query_bindings" in sql


def test_layer298_caps_each_query_cohort_to_earliest_and_latest():
    sql = _sql()

    assert "project_l_independent_served_outcome_feed_v1" in sql
    assert "rn_oldest=1 or rn_newest=1" in sql
    assert "partition by b.query_fingerprint" in sql
    assert "count(distinct query_fingerprint)" in sql


def test_layer298_requires_three_distinct_query_fingerprints():
    sql = _sql()

    assert "v_query_fingerprints >= 3" in sql
    assert "positive_renewal_requires_three_query_fingerprints" in sql
    assert "'distinctqueryfingerprints',v_query_fingerprints" in sql.replace(" ", "")


def test_layer298_rejects_request_replay_fingerprint_mismatch():
    sql = _sql()

    assert "project_l_record_served_outcome_bound_v1" in sql
    assert "project_l_layer298_fingerprint_mismatch" in sql
    assert "on conflict (outcome_id) do nothing" in sql


def test_layer298_live_companion_hashes_query_and_uses_bound_recorder():
    edge = _edge()

    assert "servedQueryFingerprint" in edge
    assert (
        'servedQueryFingerprint=await sha256' in edge
        or "servedQueryFingerprint," in edge
    )
    assert (
        '"project_l_record_served_outcome_bound_v1"' in edge
        or '"project_l_record_served_outcome_cohort_bound_v1"' in edge
    )
    assert "p_query_fingerprint:servedQueryFingerprint" in edge


def test_layer298_runtime_still_uses_governed_lease_evaluator():
    edge = _edge()

    assert '"project_l_governed_lease_evaluation_v1"' in edge
    assert "strategyLeaseEvaluation" in edge
