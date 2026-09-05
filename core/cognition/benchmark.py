"""Project L Phase 7: deterministic cognitive regression benchmarks.

The suite exercises L's production cognitive components with synthetic, traceable
fixtures. It does not call a model, Supabase or an external service. Every reported
score is calculated from executed cases; no score is configured or inferred.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from agents.rhee.rhee_v3 import calculate_memory_score, format_memory_packet
from core.cognition.controller import plan_cognition
from core.cognition.longitudinal import build_longitudinal_packet
from core.cognition.multi_agent import build_multi_agent_packet, run_parallel_foundation
from core.cognition.reflection import reflect_on_task
from core.cognition.uncertainty import assess_confidence_dimensions
from governance.cognitive_guardrails import assess_cognitive_packet


BENCHMARK_VERSION = "1.0"
BENCHMARK_DIMENSIONS = (
    "recall_accuracy",
    "chronology_accuracy",
    "identity_accuracy",
    "pattern_recognition",
    "current_vs_historical_distinction",
    "contradiction_detection",
    "source_attribution",
    "rike_reasoning_quality",
    "uncertainty_calibration",
    "specialist_routing",
    "false_memory_rate",
    "over_connection_rate",
    "reflective_metacognition",
    "governed_multi_agent_cognition",
)

REFERENCE_TIME = datetime(2026, 9, 5, tzinfo=timezone.utc)


def _context(*entries: tuple[int, str, str]) -> str:
    lines = []
    for memory_id, created_at, content in entries:
        lines.extend([
            f"90 | memory_identity | ID={memory_id} | CREATED_AT={created_at} | SOURCE_ROLE=USER",
            content,
        ])
    return "\n".join(lines)


def _case(dimension: str, name: str, run: Callable[[], tuple[bool, object, object]]) -> dict:
    try:
        passed, expected, observed = run()
        return {
            "dimension": dimension,
            "name": name,
            "passed": bool(passed),
            "expected": expected,
            "observed": observed,
            "error": None,
        }
    except Exception as exc:  # A broken benchmark must fail visibly, never disappear.
        return {
            "dimension": dimension,
            "name": name,
            "passed": False,
            "expected": "case completes without error",
            "observed": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _recall_selects_direct_fact():
    query = "When did Luella get her braces off?"
    direct = {
        "id": 1,
        "content": "Luella got her braces off on 16 June 2026.",
        "primary_subject": "Luella",
        "importance": 70,
        "salience": 70,
        "_source_role": "user",
    }
    unrelated = {
        "id": 2,
        "content": "A project architecture discussion without family information.",
        "primary_subject": "Project L",
        "importance": 100,
        "salience": 100,
        "anchor": True,
        "_source_role": "user",
    }
    scores = {
        "direct": calculate_memory_score(direct, query),
        "unrelated": calculate_memory_score(unrelated, query),
    }
    return scores["direct"] > scores["unrelated"], "direct > unrelated", scores


def _chronology_tracks_bounds():
    packet = build_longitudinal_packet(
        "How has this pattern changed over time?",
        _context(
            (1, "2026-01-10T00:00:00+00:00", "2026-01-10 The response occurred."),
            (2, "2026-03-20T00:00:00+00:00", "2026-03-20 The response occurred again."),
            (3, "2026-07-05T00:00:00+00:00", "2026-07-05 The response continued."),
        ),
        now=REFERENCE_TIME,
    )
    observed = {"first_seen": packet["first_seen"], "last_seen": packet["last_seen"]}
    expected = {"first_seen": "2026-01-10", "last_seen": "2026-07-05"}
    return observed == expected, expected, observed


def _identity_preserves_current_precedence():
    packet = build_longitudinal_packet(
        "Is this identity pattern still current?",
        _context(
            (1, "2024-01-01T00:00:00+00:00", "2024-01-01 That was an old version of me."),
            (2, "2026-08-01T00:00:00+00:00", "2026-08-01 That is not who I am now."),
        ),
        now=REFERENCE_TIME,
    )
    observed = {
        "current_identity_precedence": packet["current_identity_precedence"],
        "lifecycle_state": packet["lifecycle_state"],
    }
    expected = {"current_identity_precedence": True, "lifecycle_state": "Superseded"}
    return observed == expected, expected, observed


def _pattern_requires_corroboration():
    one = build_longitudinal_packet(
        "Is this a pattern?",
        _context((1, "2026-08-01T00:00:00+00:00", "2026-08-01 It happened once.")),
        now=REFERENCE_TIME,
    )
    two = build_longitudinal_packet(
        "Is this a pattern again?",
        _context(
            (1, "2026-07-01T00:00:00+00:00", "2026-07-01 It happened."),
            (2, "2026-08-01T00:00:00+00:00", "2026-08-01 It happened again."),
        ),
        now=REFERENCE_TIME,
    )
    observed = {
        "one_observation": one["pattern_threshold_met"],
        "two_observations": two["pattern_threshold_met"],
    }
    expected = {"one_observation": False, "two_observations": True}
    return observed == expected, expected, observed


def _historical_is_context_only():
    packet = build_longitudinal_packet(
        "Is this pattern still current over time?",
        _context(
            (1, "2023-01-01T00:00:00+00:00", "2023-01-01 It happened."),
            (2, "2023-03-01T00:00:00+00:00", "2023-03-01 It happened again."),
        ),
        now=REFERENCE_TIME,
    )
    observed = {
        "relevance": packet["current_relevance"],
        "use": packet["historical_evidence_use"],
        "pattern_threshold_met": packet["pattern_threshold_met"],
    }
    expected = {
        "relevance": "historical",
        "use": "context_only",
        "pattern_threshold_met": False,
    }
    return observed == expected, expected, observed


def _contradictions_remain_visible():
    packet = build_longitudinal_packet(
        "Has this pattern changed over time?",
        _context(
            (1, "2026-01-01T00:00:00+00:00", "2026-01-01 It happened."),
            (2, "2026-02-01T00:00:00+00:00", "2026-02-01 It happened again."),
            (3, "2026-07-01T00:00:00+00:00", "2026-07-01 It no longer happens."),
            (4, "2026-08-01T00:00:00+00:00", "2026-08-01 It has stopped."),
        ),
        now=REFERENCE_TIME,
    )
    observed = {
        "contradictions": len(packet["contradicting_episodes"]),
        "lifecycle_state": packet["lifecycle_state"],
    }
    expected = {"contradictions": 2, "lifecycle_state": "Weakening"}
    return observed == expected, expected, observed


def _source_attribution_is_exposed():
    memory = {
        "id": 44,
        "created_at": "2026-06-16T00:00:00+00:00",
        "content": "Doug supplied this fact.",
        "primary_subject": "Doug",
        "_score": 300,
        "_table": "memory_identity",
        "_source_role": "user",
        "_provenance_evidence": "raw_catchall:44",
    }
    packet = format_memory_packet("Doug fact", [memory])
    observed = {
        "user_role": "SOURCE_ROLE=USER" in packet,
        "provenance": "PROVENANCE=raw_catchall:44" in packet,
        "memory_id": "ID=44" in packet,
    }
    expected = {"user_role": True, "provenance": True, "memory_id": True}
    return observed == expected, expected, observed


def _valid_rike_packet():
    return {
        "status": "ok",
        "evidence_summary": "Two traceable records support A; one contradicts it.",
        "confidence": {"level": "medium", "score": 0.65, "basis": "Mixed evidence."},
        "uncertainties": ["A current preference remains unverified."],
        "hypotheses": [
            {
                "claim": "A is better supported.",
                "supporting_evidence": ["record:1", "record:2"],
                "contradictory_evidence": ["record:3"],
                "assumptions": ["The goal is current."],
                "alternative_explanations": ["The goal may have changed."],
                "status": "supported",
            },
            {
                "claim": "B may fit an older goal.",
                "supporting_evidence": ["record:3"],
                "contradictory_evidence": ["record:1", "record:2"],
                "assumptions": ["The old goal remains relevant."],
                "alternative_explanations": ["The old record may be superseded."],
                "status": "weakened",
            },
        ],
        "alternative_explanations": ["The goal may have changed."],
        "conclusion_change_evidence": ["A new direct statement preferring B."],
        "counterfactuals": [{
            "condition": "If the current goal preferred B",
            "expected_result": "B would receive greater support",
            "implication": "The conclusion depends on goal recency",
        }],
        "causal_assessment": {
            "relationship": "association",
            "supported_causal_claim": False,
        },
        "direct_causal_evidence": {
            "established": False,
            "verified_against_context": False,
        },
    }


def _rike_quality_gate_has_negative_control():
    valid = assess_cognitive_packet(_valid_rike_packet())
    invalid_packet = _valid_rike_packet()
    invalid_packet["hypotheses"] = invalid_packet["hypotheses"][:1]
    invalid = assess_cognitive_packet(invalid_packet)
    observed = {
        "valid_passed": valid["passed"],
        "invalid_passed": invalid["passed"],
        "invalid_issue_detected": "competing_hypotheses_missing" in invalid["issues"],
    }
    expected = {
        "valid_passed": True,
        "invalid_passed": False,
        "invalid_issue_detected": True,
    }
    return observed == expected, expected, observed


def _uncertainty_does_not_inflate_missing_recall():
    controller = plan_cognition("Deep recall my recovery history")
    packet = assess_confidence_dimensions(
        "Deep recall my recovery history",
        controller,
        {"recall_active": False, "context": ""},
        {},
        {},
        {"status": "not_required"},
    )
    observed = {
        "aggregation": packet["aggregation"],
        "retrieval_level": packet["dimensions"]["retrieval"]["level"],
        "memory_level": packet["dimensions"]["memory"]["level"],
    }
    expected = {"aggregation": "prohibited", "retrieval_level": "low", "memory_level": "low"}
    return observed == expected, expected, observed


def _specialist_routes_only_when_earned():
    current = plan_cognition("Look up today's market price")
    ordinary = plan_cognition("Hello L, how are you?")
    observed = {
        "current_evidence_specialist": current["needs"]["specialist"],
        "ordinary_specialist": ordinary["needs"]["specialist"],
    }
    expected = {"current_evidence_specialist": True, "ordinary_specialist": False}
    return observed == expected, expected, observed


def assess_claim_grounding(claims: list[str], evidence: list[str]) -> dict:
    """Return a literal grounding rate for externally supplied benchmark samples."""
    normalised_evidence = [" ".join(str(item).lower().split()) for item in evidence]
    results = []
    for claim in claims:
        clean = " ".join(str(claim).lower().split())
        supported = bool(clean) and any(clean in source for source in normalised_evidence)
        results.append({"claim": str(claim), "supported": supported})
    unsupported = sum(not item["supported"] for item in results)
    total = len(results)
    return {
        "claims": results,
        "unsupported": unsupported,
        "total": total,
        "false_memory_rate": round(unsupported / total, 4) if total else None,
    }


def _false_memory_control_is_measured():
    supported = assess_claim_grounding(
        ["Luella got her braces off on 16 June 2026."],
        ["Luella got her braces off on 16 June 2026."],
    )
    unsupported = assess_claim_grounding(
        ["Luella got her braces off on 15 June 2026."],
        ["Luella got her braces off on 16 June 2026."],
    )
    observed = {
        "grounded_rate": supported["false_memory_rate"],
        "negative_control_rate": unsupported["false_memory_rate"],
    }
    expected = {"grounded_rate": 0.0, "negative_control_rate": 1.0}
    return observed == expected, expected, observed


def _over_connection_is_blocked():
    single = build_longitudinal_packet(
        "Is this a pattern?",
        _context((1, "2026-08-01T00:00:00+00:00", "2026-08-01 One observation.")),
        now=REFERENCE_TIME,
    )
    observed_rate = 1.0 if single["pattern_threshold_met"] else 0.0
    return observed_rate == 0.0, 0.0, observed_rate


def _significant_task_is_reflected_without_auto_adjustment():
    confidence = {
        "aggregation": "prohibited",
        "dimensions": {
            name: {
                "applicable": False,
                "level": "not_applicable",
                "score": None,
                "basis": "Not applicable to this fixture.",
                "limitations": [],
            }
            for name in ("source", "retrieval", "memory", "interpretation", "reasoning", "prediction")
        },
    }
    reflection = reflect_on_task(
        "Compare these options and recommend the safer one",
        "Option A is better supported by the supplied evidence.",
        {
            "controller": {
                "substantial": True,
                "difficulty": "medium",
                "needs": {
                    "memory": False,
                    "external_evidence": False,
                    "structured_reasoning": True,
                    "longitudinal_reasoning": False,
                    "specialist": False,
                },
            },
            "route": {"rike": "active"},
            "mary": {"contradicting_episodes": []},
            "rike": {"status": "ok", "conflicts": [], "hypotheses": []},
            "confidence_dimensions": confidence,
        },
        rhee_packet={"recall_active": False, "context": "MEMORIES FOUND: 0"},
        source_reference="benchmark:reflective_metacognition",
    )
    observed = {
        "active": reflection["active"],
        "check_count": len(reflection["checks"]),
        "auto_adjusted": reflection["auto_adjusted"],
        "stored_growth": reflection["stored_growth"],
    }
    expected = {"active": True, "check_count": 8, "auto_adjusted": False, "stored_growth": False}
    return observed == expected, expected, observed


def _multi_agent_workers_are_bounded_behind_one_voice():
    foundation = run_parallel_foundation(
        "Compare the pattern over time and recommend the best supported option",
        _context(
            (1, "2026-07-01T00:00:00+00:00", "2026-07-01 It happened."),
            (2, "2026-08-01T00:00:00+00:00", "2026-08-01 It happened again."),
        ),
        structured_reasoning_required=True,
    )
    packet = build_multi_agent_packet(
        {"needs": {"memory": True, "structured_reasoning": True, "longitudinal_reasoning": True}},
        {"recall_active": True},
        {"handled": False, "capability": "l_core", "status": "not_required"},
        foundation,
        {"status": "ok"},
    )
    observed = {
        "one_voice": packet["one_voice"],
        "synthesis_owner": packet["synthesis_owner"],
        "parallel_execution": packet["parallel_execution"],
        "governance_passed": packet["governance"]["passed"],
        "worker_voice_authorities": sum(
            bool(worker["voice_authority"]) for worker in packet["workers"].values()
        ),
    }
    expected = {
        "one_voice": True,
        "synthesis_owner": "L",
        "parallel_execution": True,
        "governance_passed": True,
        "worker_voice_authorities": 0,
    }
    return observed == expected, expected, observed


CASES = (
    ("recall_accuracy", "direct_fact_outranks_unrelated_anchor", _recall_selects_direct_fact),
    ("chronology_accuracy", "first_and_last_seen_are_date_ordered", _chronology_tracks_bounds),
    ("identity_accuracy", "current_identity_supersedes_old_identity", _identity_preserves_current_precedence),
    ("pattern_recognition", "pattern_requires_two_observations", _pattern_requires_corroboration),
    ("current_vs_historical_distinction", "historical_evidence_is_context_only", _historical_is_context_only),
    ("contradiction_detection", "contradictions_drive_weakening_state", _contradictions_remain_visible),
    ("source_attribution", "role_provenance_and_id_are_exposed", _source_attribution_is_exposed),
    ("rike_reasoning_quality", "quality_gate_accepts_valid_and_rejects_invalid", _rike_quality_gate_has_negative_control),
    ("uncertainty_calibration", "missing_recall_stays_low_confidence", _uncertainty_does_not_inflate_missing_recall),
    ("specialist_routing", "specialist_activation_is_selective", _specialist_routes_only_when_earned),
    ("false_memory_rate", "unsupported_claim_negative_control", _false_memory_control_is_measured),
    ("over_connection_rate", "one_observation_is_not_a_pattern", _over_connection_is_blocked),
    ("reflective_metacognition", "significant_task_receives_governed_reflection", _significant_task_is_reflected_without_auto_adjustment),
    ("governed_multi_agent_cognition", "parallel_workers_remain_behind_one_l", _multi_agent_workers_are_bounded_behind_one_voice),
)


def benchmark_manifest() -> dict:
    return {
        "engine": "l_cognitive_benchmark",
        "version": BENCHMARK_VERSION,
        "principle": "if_i_can_see_it_its_real",
        "dimensions": list(BENCHMARK_DIMENSIONS),
        "case_count": len(CASES),
        "scoring": "calculated_only_from_executed_case_outcomes",
        "external_calls": False,
    }


def run_cognitive_benchmark() -> dict:
    """Execute the permanent suite and derive every score from case results."""
    cases = [_case(*definition) for definition in CASES]
    metrics = {}
    for dimension in BENCHMARK_DIMENSIONS:
        dimension_cases = [case for case in cases if case["dimension"] == dimension]
        passed = sum(case["passed"] for case in dimension_cases)
        total = len(dimension_cases)
        metrics[dimension] = {
            "passed": passed,
            "total": total,
            "score_pct": round(100.0 * passed / total, 2) if total else None,
            "cases": dimension_cases,
        }
    passed = sum(case["passed"] for case in cases)
    total = len(cases)
    return {
        **benchmark_manifest(),
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if passed == total else "failed",
        "overall": {
            "passed": passed,
            "total": total,
            "score_pct": round(100.0 * passed / total, 2) if total else None,
        },
        "metrics": metrics,
    }


__all__ = [
    "BENCHMARK_DIMENSIONS",
    "BENCHMARK_VERSION",
    "assess_claim_grounding",
    "benchmark_manifest",
    "run_cognitive_benchmark",
]
