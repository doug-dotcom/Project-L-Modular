# ============================================================
# OBSERVABILITY LIEUTENANT
# Privacy-safe runtime event history
# ============================================================

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from redis import Redis
from redis.exceptions import RedisError


ROOT = Path(__file__).resolve().parents[2]
EVENTS_FILE = Path(
    os.getenv(
        "SHINE_OBSERVABILITY_EVENTS_FILE",
        str(ROOT / "memory" / "observability" / "runtime_events.json"),
    )
)
REDIS_KEY = "shine:project-l:observability:events:v2"
MAX_EVENTS = 500

MEMORY_SLO_MIN_SAMPLES = 20
MEMORY_SLO_AVAILABILITY_TARGET = 0.99
MEMORY_SLO_LATENCY_TARGET_MS = 3000.0
MEMORY_SLO_HISTORY_LIMIT = 100

# Event history is operational telemetry, not memory. Keys that could carry
# user content, credentials, identifiers or private payloads are discarded.
_FORBIDDEN_KEY_FRAGMENTS = (
    "message",
    "query",
    "prompt",
    "content",
    "memory",
    "token",
    "secret",
    "password",
    "authorization",
    "owner",
    "user_id",
    "email",
    "raw",
    "text",
)

_MAX_EVENT_TYPE_CHARS = 80
_MAX_STRING_VALUE_CHARS = 160


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_key(key: Any) -> str | None:
    candidate = str(key or "").strip()
    if not candidate:
        return None
    lowered = candidate.lower()
    if any(fragment in lowered for fragment in _FORBIDDEN_KEY_FRAGMENTS):
        return None
    return candidate[:80]


def _safe_scalar(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:_MAX_STRING_VALUE_CHARS]
    return str(value)[:_MAX_STRING_VALUE_CHARS]


def _sanitize_payload(payload: Any, *, depth: int = 0) -> dict[str, Any]:
    if not isinstance(payload, dict) or depth > 2:
        return {}

    cleaned: dict[str, Any] = {}
    for raw_key, raw_value in payload.items():
        key = _safe_key(raw_key)
        if key is None:
            continue

        if isinstance(raw_value, dict) and depth < 2:
            cleaned[key] = _sanitize_payload(raw_value, depth=depth + 1)
        elif isinstance(raw_value, (list, tuple)):
            cleaned[key] = [
                _safe_scalar(item)
                for item in list(raw_value)[:20]
                if not isinstance(item, (dict, list, tuple))
            ]
        else:
            cleaned[key] = _safe_scalar(raw_value)

    return cleaned


class ObservabilityLieutenant:

    def __init__(self, *, redis_client=None, events_file: Path | None = None):
        self.name = "Observability Lieutenant"
        self.status = "active"
        self.version = "AODS66-v2"
        self._redis_override = redis_client
        self.events_file = events_file or EVENTS_FILE
        self._file_lock = threading.Lock()

    # ========================================================
    # STORAGE
    # ========================================================

    def _redis(self):
        if self._redis_override is not None:
            return self._redis_override

        url = os.getenv("REDIS_URL", "").strip()
        if not url:
            return None

        return Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            health_check_interval=30,
        )

    def _load_redis_events(self, client) -> list[dict[str, Any]] | None:
        try:
            rows = client.lrange(REDIS_KEY, 0, -1)
        except RedisError:
            return None
        events: list[dict[str, Any]] = []
        for row in rows:
            try:
                parsed = json.loads(row)
            except Exception:
                continue
            if isinstance(parsed, dict):
                events.append(parsed)
        return events[-MAX_EVENTS:]

    def _record_redis_event(self, client, event: dict[str, Any]) -> bool:
        try:
            pipe = client.pipeline(transaction=True)
            pipe.rpush(
                REDIS_KEY,
                json.dumps(event, separators=(",", ":"), ensure_ascii=False),
            )
            pipe.ltrim(REDIS_KEY, -MAX_EVENTS, -1)
            pipe.execute()
            return True
        except RedisError:
            return False

    def _load_file_events(self) -> list[dict[str, Any]]:
        with self._file_lock:
            try:
                if not self.events_file.exists():
                    return []
                parsed = json.loads(
                    self.events_file.read_text(encoding="utf-8")
                )
            except Exception:
                return []
        if not isinstance(parsed, list):
            return []
        return [
            item for item in parsed[-MAX_EVENTS:]
            if isinstance(item, dict)
        ]

    def _record_file_event(self, event: dict[str, Any]) -> bool:
        with self._file_lock:
            try:
                self.events_file.parent.mkdir(parents=True, exist_ok=True)
                events: list[dict[str, Any]] = []
                if self.events_file.exists():
                    try:
                        parsed = json.loads(
                            self.events_file.read_text(encoding="utf-8")
                        )
                        if isinstance(parsed, list):
                            events = [
                                item for item in parsed
                                if isinstance(item, dict)
                            ]
                    except Exception:
                        events = []

                events.append(event)
                events = events[-MAX_EVENTS:]
                temp = self.events_file.with_suffix(
                    self.events_file.suffix + ".tmp"
                )
                temp.write_text(
                    json.dumps(events, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                temp.replace(self.events_file)
                return True
            except Exception:
                return False

    def load_events_with_source(self) -> tuple[list[dict[str, Any]], str]:
        client = self._redis()
        if client is not None:
            redis_events = self._load_redis_events(client)
            if redis_events is not None:
                return redis_events, "railway-redis-volume"
        return self._load_file_events(), "local-file"

    def load_events(self) -> list[dict[str, Any]]:
        events, _ = self.load_events_with_source()
        return events

    # ========================================================
    # RECORD EVENT
    # ========================================================

    def record_event(self, event_type: str, payload: dict) -> dict[str, Any]:
        safe_type = str(event_type or "").strip()[:_MAX_EVENT_TYPE_CHARS]
        if not safe_type:
            return {
                "recorded": False,
                "event_type": "",
                "storage": "none",
            }

        event = {
            "timestamp": _utc_timestamp(),
            "event_type": safe_type,
            "payload": _sanitize_payload(payload),
        }

        client = self._redis()
        if client is not None and self._record_redis_event(client, event):
            return {
                "recorded": True,
                "event_type": safe_type,
                "storage": "railway-redis-volume",
            }

        recorded = self._record_file_event(event)
        return {
            "recorded": recorded,
            "event_type": safe_type,
            "storage": "local-file" if recorded else "none",
        }

    # ========================================================
    # MEMORY BRIDGE SLO
    # ========================================================

    @staticmethod
    def _memory_slo_status(
        *,
        samples: int,
        availability: float | None,
        latency_ms: float | None,
    ) -> str:
        if samples < MEMORY_SLO_MIN_SAMPLES:
            return "warming"
        if (
            availability is not None
            and availability >= MEMORY_SLO_AVAILABILITY_TARGET
            and latency_ms is not None
            and latency_ms <= MEMORY_SLO_LATENCY_TARGET_MS
        ):
            return "met"
        return "missed"

    def memory_bridge_slo_snapshot(self) -> dict[str, Any]:
        events, storage = self.load_events_with_source()

        deploy_events = [
            item
            for item in events
            if isinstance(item, dict)
            and item.get("event_type") == "memory_bridge_deploy_slo"
            and isinstance(item.get("payload"), dict)
        ][-MEMORY_SLO_HISTORY_LIMIT:]

        deploy_successes = 0
        deploy_failures = 0
        deploy_ewma_latency_ms = 0.0
        deploy_latency_samples = 0

        for item in deploy_events:
            payload = item["payload"]
            outcome = str(payload.get("outcome") or "success").strip().lower()
            if outcome == "success":
                deploy_successes += 1
                try:
                    latency_ms = float(payload.get("latency_ms"))
                except (TypeError, ValueError):
                    latency_ms = -1.0
                if latency_ms >= 0:
                    deploy_ewma_latency_ms = (
                        latency_ms
                        if deploy_latency_samples == 0
                        else deploy_ewma_latency_ms * 0.8 + latency_ms * 0.2
                    )
                    deploy_latency_samples += 1
            else:
                deploy_failures += 1

        deploy_samples = deploy_successes + deploy_failures
        deploy_availability = (
            deploy_successes / deploy_samples if deploy_samples else None
        )
        deploy_latency = (
            round(deploy_ewma_latency_ms, 1)
            if deploy_latency_samples
            else None
        )

        runtime_events = [
            item
            for item in events
            if isinstance(item, dict)
            and item.get("event_type") == "memory_bridge_runtime_rollup"
            and isinstance(item.get("payload"), dict)
        ][-MEMORY_SLO_HISTORY_LIMIT:]

        periodic_rollups = 0
        shutdown_rollups = 0
        canary_rollups = 0
        runtime_successes = 0
        runtime_failures = 0
        runtime_latency_sum_ms = 0.0
        runtime_latency_completed = 0

        for item in runtime_events:
            payload = item["payload"]
            kind = str(payload.get("rollup_kind") or "")
            if kind == "canary":
                canary_rollups += 1
                continue
            if kind == "periodic":
                periodic_rollups += 1
            elif kind == "shutdown":
                shutdown_rollups += 1
            else:
                continue

            successes = int(payload.get("successes", 0) or 0)
            failures = int(payload.get("failures", 0) or 0)
            completed = successes + failures
            runtime_successes += successes
            runtime_failures += failures

            try:
                mean_latency_ms = float(payload.get("mean_latency_ms"))
            except (TypeError, ValueError):
                mean_latency_ms = -1.0
            if completed > 0 and mean_latency_ms >= 0:
                runtime_latency_sum_ms += mean_latency_ms * completed
                runtime_latency_completed += completed

        recovery_successes = 0
        recovery_samples = 0
        for item in reversed(runtime_events):
            payload = item["payload"]
            kind = str(payload.get("rollup_kind") or "")
            if kind == "canary":
                continue
            if kind not in {"periodic", "shutdown"}:
                continue
            failures = int(payload.get("failures", 0) or 0)
            successes = int(payload.get("successes", 0) or 0)
            if failures > 0:
                break
            recovery_successes += successes
            recovery_samples += successes

        qualified_recovery_successes = 0
        qualified_recovery_samples = 0
        for item in reversed(runtime_events):
            payload = item["payload"]
            kind = str(payload.get("rollup_kind") or "")
            if kind == "canary":
                continue
            if kind not in {"periodic", "shutdown"}:
                continue
            failures = int(payload.get("failures", 0) or 0)
            successes = int(payload.get("successes", 0) or 0)
            if failures > 0:
                break
            try:
                recovery_latency_ms = float(payload.get("mean_latency_ms"))
            except (TypeError, ValueError):
                recovery_latency_ms = -1.0
            if (
                recovery_latency_ms < 0
                or recovery_latency_ms > MEMORY_SLO_LATENCY_TARGET_MS
            ):
                break
            qualified_recovery_successes += successes
            qualified_recovery_samples += successes

        runtime_samples = runtime_successes + runtime_failures
        runtime_availability = (
            runtime_successes / runtime_samples if runtime_samples else None
        )
        runtime_mean_latency_ms = (
            round(runtime_latency_sum_ms / runtime_latency_completed, 1)
            if runtime_latency_completed
            else None
        )
        runtime_status = self._memory_slo_status(
            samples=runtime_samples,
            availability=runtime_availability,
            latency_ms=runtime_mean_latency_ms,
        )
        recovery_state = (
            "healthy_streak"
            if qualified_recovery_samples >= 3
            else "recovering"
            if qualified_recovery_samples > 0
            else "latency_degraded"
            if recovery_samples > 0
            else "no_clean_runtime_samples"
        )
        operational_state = (
            "healthy"
            if runtime_status == "met"
            else "warming"
            if runtime_status == "warming"
            else "recovered_observing"
            if recovery_state == "healthy_streak"
            else "recovering"
            if recovery_state == "recovering"
            else "degraded"
        )

        return {
            "storage": storage,
            "targets": {
                "min_samples": MEMORY_SLO_MIN_SAMPLES,
                "availability": MEMORY_SLO_AVAILABILITY_TARGET,
                "latency_ms": MEMORY_SLO_LATENCY_TARGET_MS,
                "history_limit": MEMORY_SLO_HISTORY_LIMIT,
            },
            "deployment": {
                "status": self._memory_slo_status(
                    samples=deploy_samples,
                    availability=deploy_availability,
                    latency_ms=deploy_latency,
                ),
                "samples": deploy_samples,
                "successes": deploy_successes,
                "failures": deploy_failures,
                "availability": (
                    round(deploy_availability, 6)
                    if deploy_availability is not None
                    else None
                ),
                "ewma_latency_ms": deploy_latency,
            },
            "runtime": {
                "status": runtime_status,
                "samples": runtime_samples,
                "successes": runtime_successes,
                "failures": runtime_failures,
                "availability": (
                    round(runtime_availability, 6)
                    if runtime_availability is not None
                    else None
                ),
                "mean_latency_ms": runtime_mean_latency_ms,
                "periodic_rollups": periodic_rollups,
                "shutdown_rollups": shutdown_rollups,
                "canary_rollups": canary_rollups,
                "recovery_successes_since_last_failure": recovery_successes,
                "recovery_samples_since_last_failure": recovery_samples,
                "qualified_recovery_successes": qualified_recovery_successes,
                "qualified_recovery_samples": qualified_recovery_samples,
                "recovery_state": recovery_state,
                "operational_state": operational_state,
            },
        }

    # ========================================================
    # RUNTIME SNAPSHOT
    # ========================================================

    def build_runtime_snapshot(self) -> dict[str, Any]:
        events = self.load_events()
        latest = events[-10:]

        captain_counts: dict[str, int] = {}
        event_type_counts: dict[str, int] = {}

        for item in events:
            event_type = str(item.get("event_type") or "")
            if event_type:
                event_type_counts[event_type] = (
                    event_type_counts.get(event_type, 0) + 1
                )

            payload = (
                item.get("payload")
                if isinstance(item.get("payload"), dict)
                else {}
            )
            captain = payload.get("captain")
            if isinstance(captain, str) and captain:
                captain_counts[captain] = (
                    captain_counts.get(captain, 0) + 1
                )

        return {
            "total_events": len(events),
            "latest_events": latest,
            "captain_counts": captain_counts,
            "event_type_counts": event_type_counts,
        }

    # ========================================================
    # STATUS
    # ========================================================

    def runtime_status(self) -> dict[str, Any]:
        snapshot = self.build_runtime_snapshot()
        return {
            "name": self.name,
            "status": self.status,
            "version": self.version,
            "events": snapshot["total_events"],
        }


OBSERVABILITY_LIEUTENANT = ObservabilityLieutenant()
