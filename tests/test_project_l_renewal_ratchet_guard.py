from pathlib import Path

MIGRATION = Path(
    "supabase/migrations/20260929133000_project_l_layer297_renewal_ratchet_guard.sql"
)
EDGE = Path("supabase/functions/l-companion/index.ts")


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def _edge() -> str:
    return EDGE.read_text(encoding="utf-8")


def test_layer297_blocks_positive_renewal_before_final_24_hours():
    sql = _sql()

    assert "project_l_governed_lease_evaluation_v1" in sql
    assert "lease_expires_at-interval '24 hours'" in sql
    assert "positive_renewal_blocked_until_final_24_hours" in sql
    assert "'status','monitoring'" in sql
    assert "'mutationperformed',false" in sql.replace(" ", "")


def test_layer297_preserves_early_negative_revocation():
    sql = _sql()

    assert "v_quality_decay" in sql
    assert "'status','early_quality_review'" in sql
    assert "project_l_strategy_lease_status_v1" in sql
    assert "v_avg < v_quality_floor" in sql


def test_layer297_keeps_layer294_authoritative_in_renewal_window():
    sql = _sql()

    assert "'status','renewal_window_evaluation'" in sql
    assert "layer 294 remains the" in sql
    assert "authoritative renew / active / expire / revoke" in sql


def test_layer297_runtime_uses_guard_not_direct_auto_renewal():
    edge = _edge()

    assert '"project_l_governed_lease_evaluation_v1"' in edge
    assert '"project_l_auto_renewal_feed_v1"' not in edge
    assert "strategyLeaseEvaluation" in edge
    assert "p_request_id:requestId" in edge


def test_layer297_surface_is_service_role_only():
    sql = _sql()

    assert "security invoker" in sql
    assert "from public, anon, authenticated" in sql
    assert "to service_role" in sql
