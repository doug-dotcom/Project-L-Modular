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


ASSOCIATIVE_SATURATION_VERSION = "1.0"
COOLDOWN_SECONDS = 45
THREAD_TTL_SECONDS = 30 * 60
MAX_RECENT_PROBES = 6
MAX_SIGNATURE_TERMS = 12

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


class AssociativeRetrievalGovernor:
    """Bound background memory probes per conversation scope.

    The governor remembers only cue signatures/timestamps in process memory. It
    never stores the message, retrieved memory, evidence, or user state.
    """

    def __init__(self, cooldown_seconds: int = COOLDOWN_SECONDS):
        self.cooldown_seconds = max(1, int(cooldown_seconds))
        self._states: dict[str, _ScopeState] = {}
        self._lock = threading.RLock()

    def evaluate(
        self,
        scope_id: str,
        message: str,
        cognitive_plan: dict | None,
        *,
        now: float | None = None,
    ) -> dict:
        current = float(time.monotonic() if now is None else now)
        plan = cognitive_plan or {}
        needs = plan.get("needs") or {}
        signals = plan.get("signals") or {}
        associative = bool(needs.get("cue_driven_memory"))
        explicit = bool(signals.get("explicit_recall"))
        cue = plan.get("associative_cue") or {}

        base = {
            "engine": "associative_saturation_guard",
            "version": ASSOCIATIVE_SATURATION_VERSION,
            "applies": associative,
            "explicit_recall_bypass": explicit,
            "cooldown_seconds": self.cooldown_seconds,
            "durable": False,
            "stores_memory_content": False,
        }
        if explicit or not associative:
            return {
                **base,
                "allowed": True,
                "reason": "explicit_recall_bypass" if explicit else "not_applicable",
                "novelty": 1.0,
                "recent_probe_count": 0,
            }

        scope = str(scope_id or "default")[:100]
        terms = _terms(message)
        signature = _signature(message)
        cue_score = float(cue.get("score") or 0.0)

        with self._lock:
            state = self._states.get(scope)
            if state and current - state.updated_at > THREAD_TTL_SECONDS:
                state = None
                self._states.pop(scope, None)
            if state is None:
                state = _ScopeState(updated_at=current)
                self._states[scope] = state

            recent = list(state.probes)
            strongest_similarity = max(
                (_similarity(terms, item["terms"]) for item in recent),
                default=0.0,
            )
            seconds_since_last = (
                current - recent[-1]["at"] if recent else None
            )
            novelty = round(max(0.0, 1.0 - strongest_similarity), 2)

            # Strongly novel or very strong cues may bypass the ordinary cooldown.
            high_value_new_cue = cue_score >= 0.85 and novelty >= 0.45
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

            return {
                **base,
                "allowed": allowed,
                "reason": reason,
                "novelty": novelty,
                "cue_score": round(cue_score, 2),
                "strongest_recent_similarity": round(strongest_similarity, 2),
                "seconds_since_last_probe": (
                    None if seconds_since_last is None else round(seconds_since_last, 1)
                ),
                "recent_probe_count": len(state.probes),
                "high_value_new_cue": high_value_new_cue,
                "governance": {
                    "explicit_recall_never_throttled": True,
                    "background_retrieval_is_rate_limited": True,
                    "novel_material_cues_can_break_cooldown": True,
                    "message_content_is_not_stored": True,
                    "retrieved_memory_is_not_stored": True,
                    "process_memory_only": True,
                },
            }

    def reset(self, scope_id: str) -> None:
        with self._lock:
            self._states.pop(str(scope_id or "default")[:100], None)


__all__ = [
    "ASSOCIATIVE_SATURATION_VERSION",
    "AssociativeRetrievalGovernor",
    "COOLDOWN_SECONDS",
]
