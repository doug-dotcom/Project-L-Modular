from pathlib import Path

MIGRATION = Path(
    "supabase/migrations/20260929232000_project_l_memory_layer304_counterfactual_background_isolation.sql"
)
EDGE = Path("supabase/functions/l-companion/index.ts")


def _sql() -> str:
    return MIGRATION.read_text(encoding="utf-8").lower()


def _edge() -> str:
    return EDGE.read_text(encoding="utf-8")


def test_layer304_has_append_only_terminal_execution_receipts():
    sql = _sql()

    assert "project_l_adaptive_memory_counterfactual_executions" in sql
    assert "terminal_status in ('completed','timed_out','failed')" in sql
    assert "project_l_layer304_completed_quality_receipt_required" in sql
    assert "project_l_layer304_execution_replay_mismatch" in sql
    assert "grant select, insert on table public.project_l_adaptive_memory_counterfactual_executions" in sql
    assert "grant update" not in sql
    assert "grant delete" not in sql


def test_layer304_reliability_certificate_penalizes_timeouts_failures_and_missing_receipts():
    sql = _sql()

    for marker in (
        "v_admitted>=10",
        "v_terminal_coverage>=0.85",
        "v_completion_rate>=0.75",
        "v_timeout_share<=0.15",
        "v_failure_share<=0.15",
        "v_max_completed_ms<=1500",
    ):
        assert marker in sql

    assert "missingterminalreceipts" in sql.replace(" ", "")


def test_layer304_activation_requires_reliability_and_floor_304():
    sql = _sql()

    assert "configured_active_but_counterfactual_unreliable" in sql
    assert "activation_requires_counterfactual_reliability" in sql
    assert "and v_reliability_certified" in sql
    assert "'requiredlayerfloor',304" in sql.replace(" ", "")
    assert "required_layer_floor=304" in sql


def test_layer304_companion_uses_background_wait_until():
    edge = _edge()

    assert "EdgeRuntime.waitUntil" in edge
    assert "runAdaptiveShadowCounterfactualBackground" in edge
    wait_idx = edge.index("EdgeRuntime.waitUntil")
    return_idx = edge.rindex("return json(out)")
    assert wait_idx < return_idx


def test_layer304_counterfactual_background_has_evidence_deadline():
    edge = _edge()

    assert "SHADOW_COUNTERFACTUAL_EVIDENCE_DEADLINE_MS=1200" in edge
    assert "shadow_counterfactual_deadline" in edge
    assert "Promise.race" in edge
    assert '"project_l_record_adaptive_counterfactual_execution_v1"' in edge


def test_layer304_response_path_does_not_await_counterfactual_retrieval():
    edge = _edge()

    assert "shadowCounterfactualAdmitted" in edge
    assert "EdgeRuntime.waitUntil(" in edge
    assert "await runAdaptiveShadowCounterfactualBackground" not in edge
    assert "shadowCounterfactualInfluencedResponse=false" in edge


def test_layer304_completed_background_work_records_quality_before_completion_receipt():
    edge = _edge()

    quality = edge.index('"project_l_record_adaptive_shadow_counterfactual_v1"')
    completed_receipt = edge.index('await recordExecution("completed",null)')
    assert quality < completed_receipt
