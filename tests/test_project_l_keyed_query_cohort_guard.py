from pathlib import Path

MIGRATION = Path(
    "supabase/migrations/20260929143000_project_l_layer299_keyed_query_cohort_guard.sql"
)
EDGE = Path("supabase/functions/l-companion/index.ts")


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def _edge() -> str:
    return EDGE.read_text(encoding="utf-8")


def test_layer299_adds_append_only_keyed_cohort_bindings():
    sql = _sql()

    assert "project_l_retrieval_outcome_cohort_bindings" in sql
    assert "hmac-sha256-lexical-v1" in sql
    assert "canonical lexical cohort text is never persisted" in sql
    assert "grant select, insert on table public.project_l_retrieval_outcome_cohort_bindings" in sql
    assert "grant update" not in sql
    assert "grant delete" not in sql


def test_layer299_caps_each_lexical_cohort_to_earliest_and_latest():
    sql = _sql()

    assert "project_l_cohort_independent_served_outcome_feed_v1" in sql
    assert "partition by c.query_cohort_fingerprint" in sql
    assert "rn_oldest=1 or rn_newest=1" in sql


def test_layer299_requires_three_distinct_lexical_cohorts():
    sql = _sql()

    assert "v_query_cohorts >= 3" in sql
    assert "positive_renewal_requires_three_lexical_cohorts" in sql
    assert "'distinctlexicalcohorts',v_query_cohorts" in sql.replace(" ", "")


def test_layer299_rejects_exact_and_cohort_replay_mismatches():
    sql = _sql()

    assert "project_l_layer299_query_fingerprint_mismatch" in sql
    assert "project_l_layer299_cohort_fingerprint_mismatch" in sql
    assert sql.count("on conflict (outcome_id) do nothing") >= 2


def test_layer299_edge_uses_keyed_hmac_not_plain_query_sha():
    edge = _edge()

    assert 'const hmacKeyPromise=crypto.subtle.importKey(' in edge
    assert '"HMAC"' in edge
    assert "SERVICE" in edge
    assert "servedQueryFingerprint" in edge
    assert "servedQueryCohortFingerprint" in edge
    assert 'hmacSha256("layer299-exact-v1|"+norm(query))' in edge
    assert 'hmacSha256("layer299-cohort-v1|"+queryCohort)' in edge
    assert 'sha256("layer298-query-v1|"+norm(query))' not in edge


def test_layer299_edge_builds_canonical_lexical_cohort_without_persisting_text():
    edge = _edge()

    assert "QUERY_COHORT_STOP" in edge
    assert "queryCohortCanonical" in edge
    assert "cohortStem" in edge
    assert '"project_l_record_served_outcome_cohort_bound_v1"' in edge
    assert "p_query_cohort_fingerprint:servedQueryCohortFingerprint" in edge


def test_layer299_runtime_still_uses_governed_evaluator():
    edge = _edge()

    assert '"project_l_governed_lease_evaluation_v1"' in edge
    assert "strategyLeaseEvaluation" in edge
