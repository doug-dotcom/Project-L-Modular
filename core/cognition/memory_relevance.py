"""Project L Layer 12: memory relevance arbitration.

Layer 11 may retrieve associative memory from a present-moment cue. This layer
makes the next decision explicit and inspectable: surface one memory, use memory
silently, or discard it. Retrieval itself never grants publication authority.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re


MEMORY_RELEVANCE_VERSION = "1.0"
MAX_REVIEWED_EVIDENCE = 12

_SENSITIVE_TERMS = (
    "trauma", "abuse", "sexual", "sex", "suicide", "self-harm", "overdose",
    "diagnosis", "medication", "ptsd", "adhd", "autism", "debt", "claim",
    "insurance", "legal", "solicitor", "income protection", "tpd",
)
_STALE_MARKERS = (
    "superseded", "historical", "no longer", "not anymore", "used to",
    "replaced by", "old version",
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


def _overlap(message: str, passage: str) -> float:
    left = _terms(message)
    right = _terms(passage)
    if not left or not right:
        return 0.0
    return len(left & right) / max(1, min(len(left), 8))


def _parse_time(value: object) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _recency_score(row: dict, now: datetime) -> float:
    stamp = _parse_time(row.get("effective_from")) or _parse_time(row.get("created_at"))
    if not stamp:
        return 0.45
    age_days = max(0, (now - stamp).days)
    if age_days <= 30:
        return 1.0
    if age_days <= 180:
        return 0.85
    if age_days <= 365:
        return 0.7
    if age_days <= 1095:
        return 0.5
    return 0.3


def _source_quality(row: dict) -> float:
    role = _text(row.get("role")).casefold()
    authority = _text(row.get("authority")).casefold()
    if authority == "operator_curated":
        return 0.9
    if role == "user":
        return 1.0
    if role == "assistant":
        return 0.35
    return 0.55


def _sensitive(passage: str) -> bool:
    lowered = passage.casefold()
    return any(term in lowered for term in _SENSITIVE_TERMS)


def _stale_or_superseded(passage: str) -> bool:
    lowered = passage.casefold()
    return any(term in lowered for term in _STALE_MARKERS)


def build_memory_relevance_packet(
    message: str,
    cue_packet: dict | None,
    rhee_packet: dict | None,
    confidence_evidence: dict | None,
    *,
    now: datetime | None = None,
) -> dict:
    """Arbitrate associative memory into surface, silent-use or discard.

    This layer is only active for cue-driven retrieval. Explicit recall already
    has its own answer contract and should not be filtered through this policy.
    """
    cue = cue_packet or {}
    rhee = rhee_packet or {}
    confidence = confidence_evidence or {}
    reference_time = now or datetime.now(timezone.utc)
    if reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=timezone.utc)

    if not cue.get("active"):
        return {
            "engine": "memory_relevance_arbitration",
            "version": MEMORY_RELEVANCE_VERSION,
            "active": False,
            "decision": "not_required",
            "reviewed": [],
            "surface": [],
            "silent": [],
            "discard": [],
            "instruction": "Cue-driven memory arbitration was not required.",
            "governance": {
                "retrieval_is_not_surface_permission": True,
                "max_surface_memories": 1,
                "silent_use_allowed": True,
                "discard_allowed": True,
            },
        }

    permissions = confidence.get("claim_permissions") or {}
    evidence = [row for row in (rhee.get("evidence") or []) if isinstance(row, dict)][:MAX_REVIEWED_EVIDENCE]
    cue_score = float((cue.get("cue") or {}).get("score") or 0.0)
    reviewed = []

    for row in evidence:
        passage = _text(row.get("quote_source"))
        if not passage:
            continue
        lexical = _overlap(message, passage)
        source = _source_quality(row)
        recency = _recency_score(row, reference_time)
        sensitive = _sensitive(passage)
        stale = _stale_or_superseded(passage)

        # Weighted relevance is used only for arbitration, never as a truth score.
        relevance = round(
            min(1.0, (0.34 * cue_score) + (0.28 * lexical) + (0.22 * source) + (0.16 * recency)),
            2,
        )

        direct_topic_match = lexical >= 0.22
        fact_or_inference_allowed = bool(
            permissions.get("personal_fact") or permissions.get("supported_inference")
        )

        if stale and not direct_topic_match:
            disposition = "discard"
            reason = "Historical or superseded memory is not directly relevant to the present cue."
        elif sensitive and not direct_topic_match:
            disposition = "silent"
            reason = "Sensitive memory may inform context but should not be surfaced without direct relevance."
        elif relevance >= 0.78 and direct_topic_match and fact_or_inference_allowed:
            disposition = "surface"
            reason = "Strong cue match, traceable evidence and sufficient claim permission."
        elif relevance >= 0.52:
            disposition = "silent"
            reason = "Potentially useful context, but not strong enough to surface confidently."
        else:
            disposition = "discard"
            reason = "Weak or unnecessary match to the present moment."

        reviewed.append({
            "source": _text(row.get("source")),
            "disposition": disposition,
            "relevance": relevance,
            "topic_overlap": round(lexical, 2),
            "source_quality": round(source, 2),
            "recency": round(recency, 2),
            "sensitive": sensitive,
            "stale_or_superseded": stale,
            "reason": reason,
        })

    # Surface at most one item; demote additional surface candidates to silent.
    surface_candidates = sorted(
        [item for item in reviewed if item["disposition"] == "surface"],
        key=lambda item: item["relevance"],
        reverse=True,
    )
    allowed_surface = {surface_candidates[0]["source"]} if surface_candidates else set()
    for item in reviewed:
        if item["disposition"] == "surface" and item["source"] not in allowed_surface:
            item["disposition"] = "silent"
            item["reason"] = "Relevant, but another memory was more useful to surface in this turn."

    surface = [item for item in reviewed if item["disposition"] == "surface"]
    silent = [item for item in reviewed if item["disposition"] == "silent"]
    discard = [item for item in reviewed if item["disposition"] == "discard"]
    decision = "surface" if surface else "silent" if silent else "discard"

    return {
        "engine": "memory_relevance_arbitration",
        "version": MEMORY_RELEVANCE_VERSION,
        "active": True,
        "decision": decision,
        "reviewed": reviewed,
        "surface": surface,
        "silent": silent,
        "discard": discard,
        "instruction": (
            "Use this arbitration as the publication boundary for cue-driven memory. Surface at most "
            "one memory and only when it materially improves the present answer. Silent memories may "
            "shape reasoning but must not be mentioned merely because they were retrieved. Discarded "
            "memories must not influence the answer. Do not announce this arbitration or describe "
            "background retrieval unless Doug explicitly asks."
        ),
        "governance": {
            "retrieval_is_not_surface_permission": True,
            "max_surface_memories": 1,
            "provenance_considered": True,
            "recency_considered": True,
            "privacy_considered": True,
            "materiality_required": True,
            "silent_use_allowed": True,
            "discard_allowed": True,
            "score_is_not_truth_probability": True,
        },
    }


__all__ = ["MEMORY_RELEVANCE_VERSION", "build_memory_relevance_packet"]
