from pathlib import Path

from core.cognition.operational_readiness import build_operational_readiness


def memory_snapshot(state, *, historical="missed", recovery="healthy_streak", samples=40, qualified=3):
    return {
        "runtime": {
            "status": historical,
            "samples": samples,
            "operational_state": state,
            "recovery_state": recovery,
            "qualified_recovery_successes": qualified,
        }
    }


def security(*, enforced=True, ready=True):
    return {"production_enforced": enforced, "ready": ready}


def foundation(status="active"):
    return {
        "status": status,
        "attempts": 1,
        "background_retry": False,
        "retry_exhausted": False,
    }


def test_recovered_observing_is_ready_even_when_historical_slo_is_missed():
    payload, status = build_operational_readiness(
        security_gate=security(),
        memory_snapshot=memory_snapshot("recovered_observing"),
        foundation_snapshot=foundation(),
    )

    assert status == 200
    assert payload["status"] == "ready"
    assert payload["reason"] == "core-operational"
    assert payload["components"]["memory_runtime"] == {
        "required": True,
        "readiness": "ready",
        "operational_state": "recovered_observing",
        "recovery_state": "healthy_streak",
        "historical_slo_status": "missed",
        "samples": 40,
        "qualified_recovery_successes": 3,
    }


def test_recovering_memory_is_not_ready_without_failing_liveness_contract():
    payload, status = build_operational_readiness(
        security_gate=security(),
        memory_snapshot=memory_snapshot(
            "recovering",
            recovery="recovering",
            qualified=1,
        ),
        foundation_snapshot=foundation(),
    )

    assert status == 503
    assert payload["status"] == "degraded"
    assert payload["reason"] == "memory-runtime-not-ready"
    assert payload["components"]["memory_runtime"]["readiness"] == "not_ready"


def test_degraded_memory_is_not_ready():
    payload, status = build_operational_readiness(
        security_gate=security(),
        memory_snapshot=memory_snapshot(
            "degraded",
            recovery="no_clean_runtime_samples",
            qualified=0,
        ),
        foundation_snapshot=foundation(),
    )

    assert status == 503
    assert payload["status"] == "degraded"


def test_warming_memory_is_nonblocking_while_evidence_accumulates():
    payload, status = build_operational_readiness(
        security_gate=security(),
        memory_snapshot=memory_snapshot(
            "warming",
            historical="warming",
            recovery="no_clean_runtime_samples",
            samples=0,
            qualified=0,
        ),
        foundation_snapshot=foundation("checking"),
    )

    assert status == 200
    assert payload["status"] == "warming"
    assert payload["reason"] == "memory-runtime-warming"
    assert payload["components"]["foundation_authority"]["required"] is False


def test_production_security_gate_stays_fail_closed():
    payload, status = build_operational_readiness(
        security_gate=security(ready=False),
        memory_snapshot=memory_snapshot("healthy", historical="met"),
        foundation_snapshot=foundation(),
    )

    assert status == 503
    assert payload["status"] == "blocked"
    assert payload["reason"] == "production-security-gate"


def test_missing_memory_snapshot_fails_readiness_closed():
    payload, status = build_operational_readiness(
        security_gate=security(),
        memory_snapshot=None,
        foundation_snapshot=foundation(),
    )

    assert status == 503
    assert payload["components"]["memory_runtime"]["operational_state"] == "unknown"


def test_server_exposes_public_readiness_without_changing_health_liveness():
    source = Path("api/server.py").read_text()

    assert "'/readiness'" in source
    assert '@app.get("/readiness")' in source
    assert "OBSERVABILITY_LIEUTENANT.memory_bridge_slo_snapshot()" in source
    assert "build_operational_readiness(" in source
    assert "if path in {'/health', '/readiness'}" in source
    assert '@app.get("/health")' in source
