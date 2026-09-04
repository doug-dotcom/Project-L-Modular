"""Mary's bounded longitudinal interpretation stage."""

from __future__ import annotations

import re


LONGITUDINAL_SIGNALS = (
    "again", "always", "before", "change", "changed", "growth", "history",
    "keep doing", "over time", "pattern", "progress", "repeated", "trend",
    "last six months", "past six months", "last 6 months", "past 6 months",
    "report for pauline",
)


def needs_longitudinal_context(message: str) -> bool:
    text = str(message or "").lower()
    return any(signal in text for signal in LONGITUDINAL_SIGNALS)


def _evidence_lines(context: str) -> list[str]:
    lines = []
    for line in str(context or "").splitlines():
        clean = line.strip()
        if not clean:
            continue
        if re.match(r"^\d+(?:\.\d+)?\s*\|\s*memory_", clean, re.I):
            lines.append(clean[:500])
        elif "independent sources" in clean.lower() and "confidence" in clean.lower():
            lines.append(clean[:500])
        for url in re.findall(r"https?://[^\s)\]]+", clean):
            lines.append(f"external:{url[:450]}")
    return list(dict.fromkeys(lines))


def build_longitudinal_packet(message: str, evidence_context: str) -> dict:
    active = needs_longitudinal_context(message)
    evidence = _evidence_lines(evidence_context) if active else []
    enough_for_pattern = len(evidence) >= 2

    return {
        "engine": "mary",
        "version": "4.0",
        "active": active,
        "evidence_refs": evidence[:8],
        "pattern_threshold_met": enough_for_pattern,
        "instruction": (
            "Compare supporting and contradicting events across time; describe direction "
            "and confidence without treating one event as a pattern."
            if active else
            "Longitudinal interpretation was not required for this request."
        ),
        "caution": (
            "There are fewer than two traceable observations; do not assert a recurring pattern."
            if active and not enough_for_pattern else ""
        ),
    }
