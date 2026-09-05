from core.cognition.learning_engine import ingest_reflective_observation
from core.cognition.reflection import record_later_evidence, reflect_on_task


def _confidence_packet():
    return {
        "aggregation": "prohibited",
        "dimensions": {
            name: {
                "applicable": name in {"source", "retrieval", "memory", "interpretation", "reasoning"},
                "level": "medium" if name != "prediction" else "not_applicable",
                "score": 0.65 if name != "prediction" else None,
                "basis": "Traceable fixture evidence.",
                "limitations": [],
            }
            for name in ("source", "retrieval", "memory", "interpretation", "reasoning", "prediction")
        },
    }


def _significant_packet():
    return {
        "controller": {
            "substantial": True,
            "difficulty": "high",
            "needs": {
                "memory": True,
                "external_evidence": False,
                "structured_reasoning": True,
                "longitudinal_reasoning": True,
                "specialist": False,
            },
        },
        "route": {"rike": "active"},
        "mary": {"contradicting_episodes": [{"evidence_ref": "memory:3"}]},
        "rike": {
            "status": "ok",
            "conflicts": ["memory:3 conflicts"],
            "hypotheses": [],
        },
        "confidence_dimensions": _confidence_packet(),
    }


def test_phase_eight_skips_ordinary_conversation():
    reflection = reflect_on_task(
        "Hello L",
        "Hello Doug",
        {
            "controller": {"substantial": False, "needs": {}},
            "route": {"rike": "not_required"},
        },
        source_reference="chat_request:ordinary",
    )
    assert reflection["status"] == "not_required"
    assert reflection["active"] is False


def test_phase_eight_reviews_all_canonical_questions_after_significant_task():
    reflection = reflect_on_task(
        "Analyse how this pattern changed over time",
        "The current evidence supports a cautious conclusion.",
        _significant_packet(),
        rhee_packet={
            "recall_active": True,
            "context": "MEMORIES FOUND: 3\n90 | memory_identity | ID=1 | SOURCE_ROLE=USER",
        },
        source_reference="chat_request:phase8",
    )
    expected_checks = {
        "enough_evidence_retrieved",
        "over_retrieval",
        "rike_invoked_appropriately",
        "contradictory_evidence_missed",
        "confidence_calibrated",
        "doug_corrected_system",
        "later_evidence_invalidated_conclusion",
        "completed_response_available",
    }
    assert reflection["active"] is True
    assert reflection["status"] == "complete"
    assert set(reflection["checks"]) == expected_checks
    assert reflection["issues"] == []
    assert reflection["auto_adjusted"] is False
    assert reflection["stored_growth"] is False


def test_phase_eight_detects_missed_evidence_and_routing_without_hiding_failure():
    packet = _significant_packet()
    packet["route"]["rike"] = "not_required"
    packet["rike"] = {"status": "not_required", "conflicts": [], "hypotheses": []}
    reflection = reflect_on_task(
        "Analyse this pattern over time",
        "A response was completed.",
        packet,
        rhee_packet={"recall_active": False, "context": "MEMORIES FOUND: 0"},
        source_reference="chat_request:failure",
    )
    assert reflection["status"] == "attention_required"
    assert "enough_evidence_retrieved" in reflection["issues"]
    assert "rike_invoked_appropriately" in reflection["issues"]
    assert "contradictory_evidence_missed" in reflection["issues"]


def test_phase_eight_records_explicit_doug_correction_and_later_invalidation():
    reflection = reflect_on_task(
        "You got that wrong; new evidence shows the earlier conclusion changed.",
        "Thank you for correcting the record.",
        _significant_packet(),
        rhee_packet={"recall_active": True, "context": "MEMORIES FOUND: 2"},
        source_reference="chat_request:correction",
    )
    assert reflection["checks"]["doug_corrected_system"]["status"] == "observed"
    assert reflection["checks"]["later_evidence_invalidated_conclusion"]["status"] == "observed"
    assert "doug_correction_observed" in reflection["observations_for_learning"]
    assert "later_evidence_invalidation_observed" in reflection["observations_for_learning"]


def test_phase_eight_can_link_later_evidence_to_the_reflected_task():
    reflection = reflect_on_task(
        "Analyse this pattern over time",
        "The current evidence supports the conclusion.",
        _significant_packet(),
        rhee_packet={"recall_active": True, "context": "MEMORIES FOUND: 2"},
        source_reference="chat_request:original",
    )
    updated = record_later_evidence(
        reflection,
        evidence_reference="raw_catchall:991",
        basis="Doug supplied a later direct observation that contradicted the conclusion.",
        invalidated_conclusion=True,
    )
    assert updated["source_reference"] == "chat_request:original"
    assert updated["later_evidence"][0]["evidence_reference"] == "raw_catchall:991"
    assert updated["checks"]["later_evidence_invalidated_conclusion"]["status"] == "observed"
    assert updated["status"] == "attention_required"
    assert updated["auto_adjusted"] is False


def test_phase_eight_feeds_learning_engine_without_auto_promotion():
    reflection = reflect_on_task(
        "You got that wrong; analyse this again.",
        "The answer has been revised.",
        _significant_packet(),
        rhee_packet={"recall_active": True, "context": "MEMORIES FOUND: 2"},
        source_reference="chat_request:learning",
    )
    learning = ingest_reflective_observation(reflection)
    assert learning["channel"] == "reflective_metacognition"
    assert learning["status"] == "candidate_adjustment"
    assert learning["source_reference"] == "chat_request:learning"
    assert learning["requires_future_observation"] is True
    assert learning["requires_doug_approval_for_storage"] is True
    assert learning["auto_promoted"] is False
    assert learning["stored_growth"] is False


def test_phase_eight_rejects_untraceable_reflection():
    learning = ingest_reflective_observation({
        "active": True,
        "source_reference": "",
        "observations_for_learning": ["confidence_calibrated"],
    })
    assert learning["status"] == "rejected"
    assert learning["reason"] == "reflection_provenance_required"


def test_phase_eight_live_server_contract_is_wired():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "api" / "server.py").read_text(encoding="utf-8")
    assert '"version": "11.0"' in source
    assert '"self_evaluation": "reflective_metacognition_v1"' in source
    assert "reflect_on_task(" in source
    assert "ingest_reflective_observation(reflection)" in source
    assert '"reflection": cognitive_packet.get("reflection", {})' in source
    assert '"learning_feedback": cognitive_packet.get("learning_feedback", {})' in source
