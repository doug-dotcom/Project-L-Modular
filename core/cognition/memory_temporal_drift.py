"""Project L Layer 18: memory temporal drift and revalidation guard.

A past lesson can be valid in its original context and still become stale as Doug's
circumstances change. This layer checks whether an already-surfaceable associative
memory is old, superseded, or contradicted by newer relevant evidence. Earlier gates
remain ceilings: temporal review may preserve or downgrade permission, never upgrade it.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re


MEMORY_TEMPORAL_DRIFT_VERSION = "1.0"
STALE_DAYS = 365
VERY_STALE_DAYS = 1095

_UPDATE_MARKERS = (
    "now", "currently", "changed", "change", "no longer", "not anymore",
    "stopped", "started", "instead", "replaced", "superseded", "new plan",
    "these days", "since then",
)
_STOP = {
    "the", "and", "for", "with", "that", "this", "from", "have", "has",
    "had", "was", "were", "are", "is", "you", "your", "me", "my", "i",
    "it", "to", "of", "in", "on", "at", "a", "an", "as", "but", "or",
}


def _text(value: object) -> str:
    return " ".join(str(value or "").split())


def _terms(value: str) -> set[str]:
    return {
        token for token in re.findall(r"[a-z0-9']+", _text(value).casefold())
        if len(token) >= 3 and token not in _STOP
    }


def _overlap(left: str, right: str) -> float:
    a, b = _terms(left), _terms(right)
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, min(len(a), 8))


def _parse_time(row: dict) -> datetime | None:
    for key in ("effective_from", "event_date", "created_at"):
        raw = _text(row.get(key))
        if not raw:
            continue
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            try:
                parsed = datetime.fromisoformat(raw[:10])
            except ValueError:
                continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _lookup(rhee_packet: dict | None, source: str) -> dict:
    for row in (rhee_packet or {}).get("evidence") or []:
        if isinstance(row, dict) and _text(row.get("source")) == source:
            return row
    return {}


def build_memory_temporal_drift_packet(
    message: str,
    cue_packet: dict | None,
    applicability_packet: dict | None,
    rhee_packet: dict | None,
    *,
    now: datetime | None = None,
) -> dict:
    """Check whether a transferable memory is still current enough to surface."""
    cue = cue_packet or {}
    applicability = applicability_packet or {}
    if not cue.get("active") or not applicability.get("active"):
        return {
            "engine": "memory_temporal_drift_guard",
            "version": MEMORY_TEMPORAL_DRIFT_VERSION,
            "active": False,
            "decision": "not_required",
            "surface_allowed": False,
            "instruction": "Temporal drift review was not required.",
        }

    prior_decision = str(applicability.get("decision") or "discard")
    if prior_decision != "surface" or not applicability.get("surface_allowed"):
        return {
            "engine": "memory_temporal_drift_guard",
            "version": MEMORY_TEMPORAL_DRIFT_VERSION,
            "active": True,
            "decision": prior_decision if prior_decision in {"silent", "discard"} else "silent",
            "surface_allowed": False,
            "source": None,
            "reason": "Earlier gates did not authorise surfacing; temporal review cannot upgrade permission.",
            "governance": {"can_upgrade_prior_permission": False},
        }

    source = _text(applicability.get("source"))
    winner = _lookup(rhee_packet, source)
    winner_passage = _text(winner.get("quote_source"))
    winner_time = _parse_time(winner)
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    reference = reference.astimezone(timezone.utc)

    age_days = None if winner_time is None else max(0, (reference - winner_time).days)
    newer_relevant = []
    for row in (rhee_packet or {}).get("evidence") or []:
        if not isinstance(row, dict):
            continue
        other_source = _text(row.get("source"))
        if not other_source or other_source == source:
            continue
        passage = _text(row.get("quote_source"))
        stamp = _parse_time(row)
        if not passage or not stamp or (winner_time and stamp <= winner_time):
            continue
        overlap = _overlap(winner_passage or message, passage)
        present_overlap = _overlap(message, passage)
        if overlap >= 0.2 or present_overlap >= 0.2:
            newer_relevant.append({
                "source": other_source,
                "created_or_effective_at": stamp.isoformat(),
                "topic_overlap": round(overlap, 2),
                "present_overlap": round(present_overlap, 2),
                "update_marker": any(marker in passage.casefold() for marker in _UPDATE_MARKERS),
            })

    newer_relevant.sort(key=lambda item: item["created_or_effective_at"], reverse=True)
    material_update = any(
        item["update_marker"] and max(item["topic_overlap"], item["present_overlap"]) >= 0.25
        for item in newer_relevant
    )

    if material_update:
        decision = "silent"
        surface_allowed = False
        status = "newer_evidence_requires_revalidation"
        reason = "Newer relevant evidence contains a change/update signal, so the older memory should not be surfaced as current."
    elif age_days is not None and age_days >= VERY_STALE_DAYS and not newer_relevant:
        decision = "silent"
        surface_allowed = False
        status = "stale_unrevalidated"
        reason = "The memory is old and no newer relevant evidence revalidates it for the present moment."
    else:
        decision = "surface"
        surface_allowed = True
        status = "temporally_usable"
        reason = "No newer retrieved evidence materially supersedes the memory, and its age does not require suppression."

    return {
        "engine": "memory_temporal_drift_guard",
        "version": MEMORY_TEMPORAL_DRIFT_VERSION,
        "active": True,
        "decision": decision,
        "surface_allowed": surface_allowed,
        "source": source if surface_allowed else None,
        "status": status,
        "memory_age_days": age_days,
        "winner_timestamp": winner_time.isoformat() if winner_time else None,
        "newer_relevant": newer_relevant[:5],
        "material_update_found": material_update,
        "reason": reason,
        "instruction": (
            "Do not carry an old memory forward as current merely because it was once true and contextually applicable. "
            "Prefer newer relevant evidence when it indicates change. If an old memory lacks revalidation, use it only as "
            "historical context rather than a current rule. Absence of newer evidence in this bounded retrieval is not proof "
            "that nothing has changed. Earlier gates remain authoritative ceilings."
        ),
        "governance": {
            "can_upgrade_prior_permission": False,
            "old_truth_is_not_current_truth": True,
            "newer_relevant_evidence_has_priority": True,
            "historical_context_must_remain_historical": True,
            "absence_of_newer_evidence_is_not_proof_of_no_change": True,
            "revalidation_required_for_very_old_memory": True,
        },
    }


__all__ = ["MEMORY_TEMPORAL_DRIFT_VERSION", "build_memory_temporal_drift_packet"]
