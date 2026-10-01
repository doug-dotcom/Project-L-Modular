from pathlib import Path

from core.cognition.operational_readiness import build_operational_readiness


def memory_snapshot(
    state,
    *,
    historical="missed",
    recovery="healthy_streak",
    samples=40,
    qualified=3,
    required=3,
    blocker=None,
    latest_latency_ms=800.0,
):
    remaining = max(0, required - qualified)
    certified = qualified >= required
    return {
        "runtime": {
            "status": historical,
            "samples": samples,
            "operational_state": state,
            "recovery_state": recovery,
            "qualified_recovery_successes": qualified,
            "recovery_required_qualified_successes": required,
            "recovery_qualified_successes_remaining": remaining,
            "recovery_certified": certified,
            "recovery_blocker": (
                blocker
                if blocker is not None
                else "none" if certified
                else "needs-qualified-successes"
            ),
            "recovery_latency_target_ms": 3000.0,
            "latest_recovery_latency_ms": latest_latency_ms,
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


def memory_process(
    *,
    status="ready",
    circuit_state="closed",
    database_configured=True,
    retry_after=0,
    failure_streak=0,
    recovery_probe=False,
):
    return {
        "status": status,
        "circuit_state": circuit_state,
        "retry_after": retry_after,
        "failure_streak": failure_streak,
        "recovery_probe_in_progress": recovery_probe,
        "database_configured": database_configured,
    }


def test_recovered_observing_is_ready_even_when_historical_slo_is_missed():
    payload, status = build_operational_readiness(
        security_gate=security(),
        memory_process_snapshot=memory_process(),
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
        "recovery_required_qualified_successes": 3,
        "recovery_qualified_successes_remaining": 0,
        "recovery_certified": True,
        "recovery_blocker": "none",
        "recovery_latency_target_ms": 3000.0,
        "latest_recovery_latency_ms": 800.0,
    }


def test_recovering_memory_is_not_ready_without_failing_liveness_contract():
    payload, status = build_operational_readiness(
        security_gate=security(),
        memory_process_snapshot=memory_process(),
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
        memory_process_snapshot=memory_process(),
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
        memory_process_snapshot=memory_process(),
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
        memory_process_snapshot=memory_process(),
        memory_snapshot=memory_snapshot("healthy", historical="met"),
        foundation_snapshot=foundation(),
    )

    assert status == 503
    assert payload["status"] == "blocked"
    assert payload["reason"] == "production-security-gate"


def test_missing_memory_snapshot_fails_readiness_closed():
    payload, status = build_operational_readiness(
        security_gate=security(),
        memory_process_snapshot=memory_process(),
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



def test_open_memory_circuit_overrides_recovered_history():
    payload, status = build_operational_readiness(
        security_gate=security(),
        memory_process_snapshot=memory_process(
            status="protected",
            circuit_state="open",
            retry_after=8,
            failure_streak=1,
        ),
        memory_snapshot=memory_snapshot("recovered_observing"),
        foundation_snapshot=foundation(),
    )

    assert status == 503
    assert payload["status"] == "degraded"
    assert payload["reason"] == "memory-process-not-ready"
    assert payload["components"]["memory_process"] == {
        "required": True,
        "ready": False,
        "status": "protected",
        "circuit_state": "open",
        "retry_after": 8,
        "failure_streak": 1,
        "recovery_probe_in_progress": False,
        "database_configured": True,
    }
    assert (
        payload["components"]["memory_runtime"]["operational_state"]
        == "recovered_observing"
    )


def test_half_open_memory_probe_is_not_ready():
    payload, status = build_operational_readiness(
        security_gate=security(),
        memory_process_snapshot=memory_process(
            status="protected",
            circuit_state="half-open",
            failure_streak=2,
            recovery_probe=True,
        ),
        memory_snapshot=memory_snapshot("recovered_observing"),
        foundation_snapshot=foundation(),
    )

    assert status == 503
    assert payload["reason"] == "memory-process-not-ready"
    assert (
        payload["components"]["memory_process"]["recovery_probe_in_progress"]
        is True
    )


def test_unconfigured_memory_process_fails_readiness_closed():
    payload, status = build_operational_readiness(
        security_gate=security(),
        memory_process_snapshot=memory_process(
            status="degraded",
            circuit_state="closed",
            database_configured=False,
        ),
        memory_snapshot=memory_snapshot("healthy", historical="met"),
        foundation_snapshot=foundation(),
    )

    assert status == 503
    assert payload["reason"] == "memory-process-not-ready"
    assert (
        payload["components"]["memory_process"]["database_configured"]
        is False
    )


def test_missing_memory_process_snapshot_fails_readiness_closed():
    payload, status = build_operational_readiness(
        security_gate=security(),
        memory_process_snapshot=None,
        memory_snapshot=memory_snapshot("healthy", historical="met"),
        foundation_snapshot=foundation(),
    )

    assert status == 503
    assert payload["reason"] == "memory-process-not-ready"
    assert payload["components"]["memory_process"]["status"] == "unknown"


def test_server_readiness_reads_current_memory_process_snapshot():
    source = Path("api/server.py").read_text()

    assert "memory_bridge_process_snapshot" in source
    assert "memory_process_snapshot=memory_bridge_process_snapshot()" in source



def test_recovering_readiness_explains_certification_gap():
    payload, status = build_operational_readiness(
        security_gate=security(),
        memory_process_snapshot=memory_process(),
        memory_snapshot=memory_snapshot(
            "recovering",
            recovery="recovering",
            qualified=1,
            blocker="needs-qualified-successes",
            latest_latency_ms=1988.9,
        ),
        foundation_snapshot=foundation(),
    )

    assert status == 503
    memory = payload["components"]["memory_runtime"]
    assert memory["qualified_recovery_successes"] == 1
    assert memory["recovery_required_qualified_successes"] == 3
    assert memory["recovery_qualified_successes_remaining"] == 2
    assert memory["recovery_certified"] is False
    assert memory["recovery_blocker"] == "needs-qualified-successes"
    assert memory["recovery_latency_target_ms"] == 3000.0
    assert memory["latest_recovery_latency_ms"] == 1988.9
