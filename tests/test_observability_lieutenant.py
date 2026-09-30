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
