"""Project L Layer 14: associative retrieval saturation and cooldown guard.

Cue-driven retrieval should feel selective, not twitchy. This process-memory
service regulates only background associative retrieval. Explicit recall always
bypasses it. Nothing here is durable and no memory content is stored.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from hashlib import sha256
import re
import threading
import time


ASSOCIATIVE_SATURATION_VERSION = "1.1"
COOLDOWN_SECONDS = 45
THREAD_TTL_SECONDS = 30 * 60
MAX_RECENT_PROBES = 6
MAX_SIGNATURE_TERMS = 12
IDEMPOTENCE_SECONDS = 2.0

_STOP = {
    "the", "and", "for", "with", "that", "this", "from", "have", "has",
    "had", "was", "were", "are", "is", "you", "your", "me", "my", "i",
    "it", "to", "of", "in", "on", "at", "a", "an", "as", "but", "or",
    "just", "really", "very", "feel", "feeling", "felt",
}


def _terms(message: str) -> tuple[str, ...]:
    tokens = [
        token for token in re.findall(r"[a-z0-9']+", str(message or "").casefold())
        if len(token) >= 3 and token not in _STOP
    ]
    return tuple(dict.fromkeys(tokens))[:MAX_SIGNATURE_TERMS]


def _signature(message: str) -> str:
    return sha256("|".join(_terms(message)).encode("utf-8")).hexdigest()[:16]


def _similarity(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    a, b = set(left), set(right)
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, min(len(a), len(b)))


@dataclass
class _ScopeState:
    updated_at: float
    probes: deque = field(default_factory=lambda: deque(maxlen=MAX_RECENT_PROBES))
    last_signature: str = ""
    last_result: dict = field(default_factory=dict)
    last_evaluated_at: float = 0.0


class AssociativeRetrievalGovernor:
    """Bound background memory probes per conversation scope.

    The governor remembers only cue signatures/timestamps in process memory. It
    never stores the message, retrieved memory, evidence, or user state.
    """

    def __init__(self, cooldown_seconds: int = COOLDOWN_SECONDS):
        self.cooldown_seconds = max(1, int(cooldown_seconds))
        self._states: dict[str, _ScopeState] = {}
        self._lock = threading.RLock()

    def evaluate_cue(
        self,
        scope_id: str,
        message: str,
        cue_score: float,
        *,
        now: float | None = None,
    ) -> dict:
        """Govern one already-detected associative cue before retrieval.

        Repeated evaluation of the same turn is idempotent so controller and
        evidence-policy calls cannot accidentally consume multiple cooldown slots.
        """
        current = float(time.monotonic() if now is None else now)
        scope = str(scope_id or "default")[:100]
        terms = _terms(message)
        signature = _signature(message)
        score = max(0.0, min(1.0, float(cue_score or 0.0)))

        base = {
            "engine": "associative_saturation_guard",
            "version": ASSOCIATIVE_SATURATION_VERSION,
            "applies": True,
            "explicit_recall_bypass": False,
            "cooldown_seconds": self.cooldown_seconds,
            "durable": False,
            "stores_memory_content": False,
        }

        with self._lock:
            state = self._states.get(scope)
            if state and current - state.updated_at > THREAD_TTL_SECONDS:
                state = None
                self._states.pop(scope, None)
            if state is None:
                state = _ScopeState(updated_at=current)
                self._states[scope] = state

            if (
                state.last_signature == signature
                and current - state.last_evaluated_at <= IDEMPOTENCE_SECONDS
                and state.last_result
            ):
                return {**state.last_result, "idempotent_reuse": True}

            recent = list(state.probes)
            strongest_similarity = max(
                (_similarity(terms, item["terms"]) for item in recent),
                default=0.0,
            )
            seconds_since_last = current - recent[-1]["at"] if recent else None
            novelty = round(max(0.0, 1.0 - strongest_similarity), 2)

            high_value_new_cue = score >= 0.85 and novelty >= 0.45
            within_cooldown = (
                seconds_since_last is not None
                and seconds_since_last < self.cooldown_seconds
            )
            repeated_thread = strongest_similarity >= 0.72
            saturated = len(recent) >= 3 and repeated_thread

            if within_cooldown and repeated_thread and not high_value_new_cue:
                allowed = False
                reason = "cooldown_repeated_cue"
            elif saturated and novelty < 0.35 and not high_value_new_cue:
                allowed = False
                reason = "thread_already_checked"
            else:
                allowed = True
                reason = "novel_or_material_cue"
                state.probes.append({
                    "at": current,
                    "signature": signature,
                    "terms": terms,
                })
                state.updated_at = current

            result = {
                **base,
                "allowed": allowed,
                "reason": reason,
                "novelty": novelty,
                "cue_score": round(score, 2),
                "strongest_recent_similarity": round(strongest_similarity, 2),
                "seconds_since_last_probe": (
                    None if seconds_since_last is None else round(seconds_since_last, 1)
                ),
                "recent_probe_count": len(state.probes),
                "high_value_new_cue": high_value_new_cue,
                "idempotent_reuse": False,
                "governance": {
                    "explicit_recall_never_throttled": True,
                    "background_retrieval_is_rate_limited": True,
                    "novel_material_cues_can_break_cooldown": True,
                    "message_content_is_not_stored": True,
                    "retrieved_memory_is_not_stored": True,
                    "process_memory_only": True,
                },
            }
            state.last_signature = signature
            state.last_result = dict(result)
            state.last_evaluated_at = current
            return result

    def evaluate(
        self,
        scope_id: str,
        message: str,
        cognitive_plan: dict | None,
        *,
        now: float | None = None,
    ) -> dict:
        plan = cognitive_plan or {}
        needs = plan.get("needs") or {}
        signals = plan.get("signals") or {}
        associative = bool(needs.get("cue_driven_memory"))
        explicit = bool(signals.get("explicit_recall"))
        cue = plan.get("associative_cue") or {}

        if explicit or not associative:
            return {
                "engine": "associative_saturation_guard",
                "version": ASSOCIATIVE_SATURATION_VERSION,
                "applies": associative,
                "explicit_recall_bypass": explicit,
                "allowed": True,
                "reason": "explicit_recall_bypass" if explicit else "not_applicable",
                "novelty": 1.0,
                "recent_probe_count": 0,
                "cooldown_seconds": self.cooldown_seconds,
                "durable": False,
                "stores_memory_content": False,
            }

        return self.evaluate_cue(
            scope_id,
            message,
            float(cue.get("score") or 0.0),
            now=now,
        )

    def reset(self, scope_id: str) -> None:
        with self._lock:
            self._states.pop(str(scope_id or "default")[:100], None)


def saturation_manifest() -> dict:
    return {
        "engine": "associative_saturation_guard",
        "version": ASSOCIATIVE_SATURATION_VERSION,
        "cooldown_seconds": COOLDOWN_SECONDS,
        "thread_ttl_seconds": THREAD_TTL_SECONDS,
        "max_recent_probes": MAX_RECENT_PROBES,
        "durable": False,
        "stored": "cue_signatures_and_timestamps_only",
        "explicit_recall_bypass": True,
    }


__all__ = [
    "ASSOCIATIVE_SATURATION_VERSION",
    "AssociativeRetrievalGovernor",
    "COOLDOWN_SECONDS",
    "saturation_manifest",
]
