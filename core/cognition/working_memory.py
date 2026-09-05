"""Project L Phase 10: bounded, disposable cognitive working memory.

This service carries only the active operational thread. It never writes to
Supabase or any other durable store, expires automatically, and can be rebuilt
from the current turn plus governed evidence packets.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import re
from threading import RLock


WORKING_MEMORY_VERSION = "1.0"
DEFAULT_TTL_SECONDS = 30 * 60
MAX_ITEMS = 8
MAX_TEXT_LENGTH = 500


def _utc_now(value: datetime | None = None) -> datetime:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _clip(value: object, limit: int = MAX_TEXT_LENGTH) -> str:
    return " ".join(str(value or "").split())[:limit]


def _bounded_unique(items: list[str], limit: int = MAX_ITEMS) -> list[str]:
    result = []
    seen = set()
    for item in reversed(items):
        clean = _clip(item)
        key = clean.casefold()
        if clean and key not in seen:
            seen.add(key)
            result.append(clean)
        if len(result) >= limit:
            break
    return list(reversed(result))


def _conversation_phase(message: str) -> str:
    text = str(message or "").casefold()
    if any(word in text for word in ("launch", "deploy", "authorised", "authorized", "approved", " go")):
        return "execution"
    if any(word in text for word in ("review", "audit", "check", "how did", "status")):
        return "review"
    if any(word in text for word in ("plan", "design", "map", "roadmap")):
        return "planning"
    if any(word in text for word in ("finished", "complete", "thanks", "thank you")):
        return "closure"
    return "active_conversation"


def _entities(message: str) -> list[str]:
    text = str(message or "")
    candidates = re.findall(r"\b(?:[A-Z]{2,}|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b", text)
    for literal in ("Project L", "Doug", "L", "Rhee", "Mary", "RIKE", "Carol", "Sara", "Quinn", "Fiona"):
        if re.search(rf"(?<!\w){re.escape(literal)}(?!\w)", text, re.IGNORECASE):
            candidates.append(literal)
    excluded = {"The", "This", "That", "Can", "Could", "Please", "Yes", "No", "Hey"}
    return _bounded_unique([item for item in candidates if item not in excluded], 12)


def _questions(message: str) -> list[str]:
    text = _clip(message)
    if not text:
        return []
    parts = re.split(r"(?<=[?.!])\s+", text)
    interrogatives = ("who ", "what ", "when ", "where ", "why ", "how ", "can ", "could ", "should ", "is ", "are ", "do ", "does ")
    return [part for part in parts if "?" in part or part.casefold().startswith(interrogatives)]


def _explicit_decisions(message: str) -> list[str]:
    text = _clip(message)
    lower = text.casefold()
    markers = ("authorised", "authorized", "approved", "i decided", "we decided", "go with", "launch", "deploy")
    return [text] if text and any(marker in lower for marker in markers) else []


def _temporary_assumptions(message: str) -> list[str]:
    text = _clip(message)
    lower = text.casefold()
    markers = ("assuming", "assume ", "for now", "probably", "i think", "my guess")
    return [text] if text and any(marker in lower for marker in markers) else []


def _goal(message: str, prior_goal: str = "") -> str:
    text = _clip(message)
    continuation = re.fullmatch(
        r"(?:yes|yep|approved|authorised|authorized|go|\d+\s+go|launch(?:\s+it)?|continue)[\s.!👊👍]*",
        text,
        flags=re.IGNORECASE,
    )
    if continuation and prior_goal:
        return prior_goal
    return text


def _evidence_receipts(rhee_packet: dict, capability_packet: dict) -> list[dict]:
    receipts = []
    rhee = rhee_packet or {}
    context = str(rhee.get("context") or "")
    if rhee.get("recall_active") or context:
        receipts.append({
            "packet": "rhee",
            "active": bool(rhee.get("recall_active")),
            "deep_recall": bool(rhee.get("deep_recall")),
            "context_size": len(context),
            "content_digest": sha256(context.encode("utf-8")).hexdigest()[:16] if context else "",
        })
    capability = capability_packet or {}
    if capability.get("handled"):
        receipts.append({
            "packet": "capability",
            "capability": _clip(capability.get("capability"), 100),
            "status": _clip(capability.get("status"), 100),
        })
    return receipts[-MAX_ITEMS:]


class ActiveContextService:
    """Thread-safe ephemeral state keyed by a bounded conversation scope."""

    def __init__(self, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self.ttl_seconds = max(60, int(ttl_seconds))
        self._states: dict[str, dict] = {}
        self._lock = RLock()

    def begin_turn(
        self,
        scope_id: str,
        message: str,
        cognitive_plan: dict,
        rhee_packet: dict,
        capability_packet: dict,
        request_id: str = "",
        now: datetime | None = None,
    ) -> dict:
        current = _utc_now(now)
        scope = _clip(scope_id, 100) or "default"
        with self._lock:
            prior = deepcopy(self._states.get(scope) or {})
            expires_at = prior.get("expires_at")
            expired = bool(expires_at and datetime.fromisoformat(expires_at) <= current)
            if expired:
                prior = {}

            decisions = _bounded_unique(
                list(prior.get("recent_decisions") or []) + _explicit_decisions(message)
            )
            questions = _bounded_unique(
                list(prior.get("unresolved_questions") or []) + _questions(message)
            )
            assumptions = _bounded_unique(
                list(prior.get("temporary_assumptions") or []) + _temporary_assumptions(message)
            )
            entities = _bounded_unique(
                list(prior.get("active_entities") or []) + _entities(message), 12
            )
            evidence = _evidence_receipts(rhee_packet, capability_packet)
            generation = int(prior.get("generation") or 0) + 1
            plan = cognitive_plan or {}
            state = {
                "engine": "cognitive_working_memory",
                "version": WORKING_MEMORY_VERSION,
                "status": "rebuilt_after_expiry" if expired else "active",
                "scope": scope,
                "generation": generation,
                "current_goal": _goal(message, str(prior.get("current_goal") or "")),
                "active_task": _clip(plan.get("problem_type") or "conversation", 120),
                "active_entities": entities,
                "recent_decisions": decisions,
                "unresolved_questions": questions,
                "temporary_assumptions": assumptions,
                "conversation_phase": _conversation_phase(message),
                "active_evidence_packets": evidence,
                "request_id": _clip(request_id, 100),
                "created_at": prior.get("created_at") or current.isoformat(),
                "updated_at": current.isoformat(),
                "expires_at": (current + timedelta(seconds=self.ttl_seconds)).isoformat(),
                "governance": {
                    "durable": False,
                    "rebuildable": True,
                    "storage": "process_memory_only",
                    "database_writes": 0,
                    "bounded": True,
                    "ttl_seconds": self.ttl_seconds,
                    "max_items_per_list": MAX_ITEMS,
                    "evidence_content_stored": False,
                    "automatic_promotion": False,
                },
            }
            self._states[scope] = deepcopy(state)
            return state

    def complete_turn(
        self,
        scope_id: str,
        reply: str,
        unresolved: bool = False,
        now: datetime | None = None,
    ) -> dict:
        current = _utc_now(now)
        scope = _clip(scope_id, 100) or "default"
        with self._lock:
            state = deepcopy(self._states.get(scope) or {})
            if not state:
                return {}
            failed = str(reply or "").startswith("AI ERROR:") or not str(reply or "").strip()
            if not unresolved and not failed:
                state["unresolved_questions"] = []
            state["status"] = "attention_required" if failed else "active"
            state["updated_at"] = current.isoformat()
            state["expires_at"] = (current + timedelta(seconds=self.ttl_seconds)).isoformat()
            self._states[scope] = deepcopy(state)
            return state

    def snapshot(self, scope_id: str, now: datetime | None = None) -> dict:
        current = _utc_now(now)
        scope = _clip(scope_id, 100) or "default"
        with self._lock:
            state = deepcopy(self._states.get(scope) or {})
            if state and datetime.fromisoformat(state["expires_at"]) <= current:
                self._states.pop(scope, None)
                return {}
            return state

    def reset(self, scope_id: str) -> None:
        scope = _clip(scope_id, 100) or "default"
        with self._lock:
            self._states.pop(scope, None)


__all__ = [
    "ActiveContextService",
    "DEFAULT_TTL_SECONDS",
    "MAX_ITEMS",
    "WORKING_MEMORY_VERSION",
]
