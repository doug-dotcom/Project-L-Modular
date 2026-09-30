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

    def load_events(self) -> list[dict[str, Any]]:
        client = self._redis()
        if client is not None:
            redis_events = self._load_redis_events(client)
            if redis_events is not None:
                return redis_events
        return self._load_file_events()

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
