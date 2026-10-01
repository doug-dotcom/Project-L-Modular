import json
from pathlib import Path

from orchestration.lieutenants.observability_lieutenant import (
    MAX_EVENTS,
    REDIS_KEY,
    ObservabilityLieutenant,
)


class FakePipeline:
    def __init__(self, redis):
        self.redis = redis
        self.ops = []

    def rpush(self, key, value):
        self.ops.append(("rpush", key, value))
        return self

    def ltrim(self, key, start, stop):
        self.ops.append(("ltrim", key, start, stop))
        return self

    def execute(self):
        for op in self.ops:
            if op[0] == "rpush":
                _, key, value = op
                self.redis.rows.setdefault(key, []).append(value)
            elif op[0] == "ltrim":
                _, key, start, stop = op
                rows = self.redis.rows.setdefault(key, [])
                if start < 0:
                    start = max(len(rows) + start, 0)
                if stop < 0:
                    stop = len(rows) + stop
                self.redis.rows[key] = rows[start:stop + 1]
        return [True] * len(self.ops)


class FakeRedis:
    def __init__(self):
        self.rows = {}

    def pipeline(self, transaction=True):
        assert transaction is True
        return FakePipeline(self)

    def lrange(self, key, start, stop):
        rows = self.rows.get(key, [])
        if stop == -1:
            return list(rows[start:])
        return list(rows[start:stop + 1])


def test_observability_sanitizes_private_runtime_payload(tmp_path):
    lieutenant = ObservabilityLieutenant(
        events_file=tmp_path / "events.json"
    )

    result = lieutenant.record_event(
        "runtime_process",
        {
            "captain": "Emily",
            "handled": True,
            "input_chars": 42,
            "message": "PRIVATE USER MESSAGE",
            "query": "PRIVATE QUERY",
            "owner_id": "PRIVATE OWNER",
            "token": "PRIVATE TOKEN",
        },
    )

    assert result["recorded"] is True
    assert result["storage"] == "local-file"

    events = lieutenant.load_events()
    assert len(events) == 1
    payload = events[0]["payload"]
    assert payload == {
        "captain": "Emily",
        "handled": True,
        "input_chars": 42,
    }
    raw = json.dumps(events)
    assert "PRIVATE USER MESSAGE" not in raw
    assert "PRIVATE QUERY" not in raw
    assert "PRIVATE OWNER" not in raw
    assert "PRIVATE TOKEN" not in raw


def test_observability_uses_redis_history_when_available(tmp_path):
    redis = FakeRedis()
    lieutenant = ObservabilityLieutenant(
        redis_client=redis,
        events_file=tmp_path / "events.json",
    )

    result = lieutenant.record_event(
        "memory_bridge_deploy_slo",
        {
            "records": 1,
            "success_rate": 1.0,
            "latency_ms": 652.2,
            "slo_status": "warming",
        },
    )

    assert result == {
        "recorded": True,
        "event_type": "memory_bridge_deploy_slo",
        "storage": "railway-redis-volume",
    }
    assert REDIS_KEY in redis.rows
    assert not (tmp_path / "events.json").exists()

    events = lieutenant.load_events()
    assert len(events) == 1
    assert events[0]["payload"]["latency_ms"] == 652.2
    assert events[0]["payload"]["slo_status"] == "warming"


def test_observability_trims_redis_history_to_bounded_retention(tmp_path):
    redis = FakeRedis()
    lieutenant = ObservabilityLieutenant(
        redis_client=redis,
        events_file=tmp_path / "events.json",
    )

    for index in range(MAX_EVENTS + 20):
        result = lieutenant.record_event(
            "test_event",
            {"sequence": index},
        )
        assert result["recorded"] is True

    events = lieutenant.load_events()
    assert len(events) == MAX_EVENTS
    assert events[0]["payload"]["sequence"] == 20
    assert events[-1]["payload"]["sequence"] == MAX_EVENTS + 19


def test_observability_runtime_snapshot_counts_event_types(tmp_path):
    lieutenant = ObservabilityLieutenant(
        events_file=tmp_path / "events.json"
    )

    lieutenant.record_event(
        "runtime_process",
        {"captain": "Emily", "handled": True},
    )
    lieutenant.record_event(
        "runtime_process",
        {"captain": "Emily", "handled": False},
    )
    lieutenant.record_event(
        "memory_bridge_deploy_slo",
        {"latency_ms": 500.0},
    )

    snapshot = lieutenant.build_runtime_snapshot()

    assert snapshot["total_events"] == 3
    assert snapshot["captain_counts"] == {"Emily": 2}
    assert snapshot["event_type_counts"] == {
        "runtime_process": 2,
        "memory_bridge_deploy_slo": 1,
    }
    assert lieutenant.runtime_status()["version"] == "AODS66-v2"



def test_memory_bridge_slo_snapshot_uses_one_durable_source_and_excludes_canary(tmp_path):
    redis = FakeRedis()
    lieutenant = ObservabilityLieutenant(
        redis_client=redis,
        events_file=tmp_path / "events.json",
    )

    lieutenant.record_event(
        "memory_bridge_deploy_slo",
        {"latency_ms": 1000.0},
    )
    lieutenant.record_event(
        "memory_bridge_deploy_slo",
        {
            "outcome": "failure",
            "failure_stage": "retrieval-unavailable",
        },
    )
    lieutenant.record_event(
        "memory_bridge_runtime_rollup",
        {
            "rollup_kind": "periodic",
            "successes": 2,
            "failures": 0,
            "mean_latency_ms": 400.0,
        },
    )
    lieutenant.record_event(
        "memory_bridge_runtime_rollup",
        {
            "rollup_kind": "shutdown",
            "successes": 1,
            "failures": 1,
            "mean_latency_ms": 600.0,
        },
    )
    lieutenant.record_event(
        "memory_bridge_runtime_rollup",
        {
            "rollup_kind": "canary",
            "successes": 50,
            "failures": 0,
            "mean_latency_ms": 10.0,
        },
    )

    snapshot = lieutenant.memory_bridge_slo_snapshot()

    assert snapshot["storage"] == "railway-redis-volume"
    assert snapshot["targets"] == {
        "min_samples": 20,
        "availability": 0.99,
        "latency_ms": 3000.0,
        "history_limit": 100,
    }

    deploy = snapshot["deployment"]
    assert deploy["status"] == "warming"
    assert deploy["samples"] == 2
    assert deploy["successes"] == 1
    assert deploy["failures"] == 1
    assert deploy["availability"] == 0.5
    assert deploy["ewma_latency_ms"] == 1000.0

    runtime = snapshot["runtime"]
    assert runtime["status"] == "warming"
    assert runtime["samples"] == 4
    assert runtime["successes"] == 3
    assert runtime["failures"] == 1
    assert runtime["availability"] == 0.75
    assert runtime["mean_latency_ms"] == 500.0
    assert runtime["periodic_rollups"] == 1
    assert runtime["shutdown_rollups"] == 1
    assert runtime["canary_rollups"] == 1


def test_memory_bridge_slo_snapshot_reports_met_and_missed_after_baseline(tmp_path):
    redis = FakeRedis()
    lieutenant = ObservabilityLieutenant(
        redis_client=redis,
        events_file=tmp_path / "events.json",
    )

    lieutenant.record_event(
        "memory_bridge_runtime_rollup",
        {
            "rollup_kind": "periodic",
            "successes": 20,
            "failures": 0,
            "mean_latency_ms": 800.0,
        },
    )
    assert lieutenant.memory_bridge_slo_snapshot()["runtime"]["status"] == "met"

    redis.rows.clear()
    lieutenant.record_event(
        "memory_bridge_runtime_rollup",
        {
            "rollup_kind": "periodic",
            "successes": 19,
            "failures": 1,
            "mean_latency_ms": 800.0,
        },
    )
    missed_availability = lieutenant.memory_bridge_slo_snapshot()["runtime"]
    assert missed_availability["status"] == "missed"
    assert missed_availability["availability"] == 0.95

    redis.rows.clear()
    lieutenant.record_event(
        "memory_bridge_runtime_rollup",
        {
            "rollup_kind": "shutdown",
            "successes": 20,
            "failures": 0,
            "mean_latency_ms": 3500.0,
        },
    )
    missed_latency = lieutenant.memory_bridge_slo_snapshot()["runtime"]
    assert missed_latency["status"] == "missed"
    assert missed_latency["mean_latency_ms"] == 3500.0



def test_memory_bridge_recovery_certification_explains_remaining_evidence(tmp_path):
    lieutenant = ObservabilityLieutenant(
        events_file=tmp_path / "events.json"
    )
    lieutenant.record_event(
        "memory_bridge_runtime_rollup",
        {
            "rollup_kind": "periodic",
            "successes": 19,
            "failures": 1,
            "mean_latency_ms": 900.0,
        },
    )
    lieutenant.record_event(
        "memory_bridge_runtime_rollup",
        {
            "rollup_kind": "periodic",
            "successes": 1,
            "failures": 0,
            "mean_latency_ms": 1988.9,
        },
    )

    runtime = lieutenant.memory_bridge_slo_snapshot()["runtime"]

    assert runtime["qualified_recovery_successes"] == 1
    assert runtime["qualified_recovery_samples"] == 1
    assert runtime["recovery_required_qualified_successes"] == 3
    assert runtime["recovery_qualified_successes_remaining"] == 2
    assert runtime["recovery_certified"] is False
    assert runtime["recovery_blocker"] == "needs-qualified-successes"
    assert runtime["recovery_latency_target_ms"] == 3000.0
    assert runtime["latest_recovery_latency_ms"] == 1988.9
    assert runtime["recovery_state"] == "recovering"
    assert runtime["operational_state"] == "recovering"


def test_memory_bridge_recovery_certification_reports_latency_blocker(tmp_path):
    lieutenant = ObservabilityLieutenant(
        events_file=tmp_path / "events.json"
    )
    lieutenant.record_event(
        "memory_bridge_runtime_rollup",
        {
            "rollup_kind": "periodic",
            "successes": 19,
            "failures": 1,
            "mean_latency_ms": 900.0,
        },
    )
    lieutenant.record_event(
        "memory_bridge_runtime_rollup",
        {
            "rollup_kind": "periodic",
            "successes": 2,
            "failures": 0,
            "mean_latency_ms": 3500.0,
        },
    )

    runtime = lieutenant.memory_bridge_slo_snapshot()["runtime"]

    assert runtime["qualified_recovery_successes"] == 0
    assert runtime["recovery_qualified_successes_remaining"] == 3
    assert runtime["recovery_certified"] is False
    assert runtime["recovery_blocker"] == "latency-above-target"
    assert runtime["latest_recovery_latency_ms"] == 3500.0
    assert runtime["recovery_state"] == "latency_degraded"
    assert runtime["operational_state"] == "degraded"


def test_memory_bridge_recovery_certification_is_earned_at_three_clean_successes(tmp_path):
    lieutenant = ObservabilityLieutenant(
        events_file=tmp_path / "events.json"
    )
    lieutenant.record_event(
        "memory_bridge_runtime_rollup",
        {
            "rollup_kind": "periodic",
            "successes": 3,
            "failures": 0,
            "mean_latency_ms": 750.0,
        },
    )

    runtime = lieutenant.memory_bridge_slo_snapshot()["runtime"]

    assert runtime["qualified_recovery_successes"] == 3
    assert runtime["recovery_qualified_successes_remaining"] == 0
    assert runtime["recovery_certified"] is True
    assert runtime["recovery_blocker"] == "none"
    assert runtime["recovery_state"] == "healthy_streak"



def test_memory_bridge_warming_still_exposes_recovery_gap(tmp_path):
    lieutenant = ObservabilityLieutenant(
        events_file=tmp_path / "events.json"
    )
    lieutenant.record_event(
        "memory_bridge_runtime_rollup",
        {
            "rollup_kind": "periodic",
            "successes": 1,
            "failures": 0,
            "mean_latency_ms": 700.0,
        },
    )

    runtime = lieutenant.memory_bridge_slo_snapshot()["runtime"]

    assert runtime["status"] == "warming"
    assert runtime["operational_state"] == "warming"
    assert runtime["qualified_recovery_successes"] == 1
    assert runtime["recovery_qualified_successes_remaining"] == 2
    assert runtime["recovery_blocker"] == "needs-qualified-successes"
