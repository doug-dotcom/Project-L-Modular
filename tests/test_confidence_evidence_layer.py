from core.cognition.confidence_evidence import build_confidence_evidence_packet


def dims(**levels):
    names = ("source", "retrieval", "memory", "interpretation", "reasoning", "prediction")
    return {
        "dimensions": {
            name: {
                "applicable": name in levels,
                "level": levels.get(name, "not_applicable"),
                "score": 0.8 if levels.get(name) == "high" else 0.6 if levels.get(name) == "medium" else 0.2,
                "basis": "test",
                "limitations": [],
            }
            for name in names
        }
    }


def evidence(source="memory_health:1"):
    return {"recall_active": True, "evidence": [{"source": source, "quote_source": "Doug reported a fact.", "role": "user"}]}


def test_traceable_personal_fact_requires_source_retrieval_and_memory_support():
    packet = build_confidence_evidence_packet(
        dims(source="high", retrieval="high", memory="high"),
        evidence(),
        {},
    )
    assert packet["claim_permissions"]["personal_fact"] is True
    assert "fact" in packet["permitted_claim_kinds"]


def test_low_retrieval_blocks_fact_even_with_a_source_record():
    packet = build_confidence_evidence_packet(
        dims(source="high", retrieval="low", memory="high"),
        evidence(),
        {},
    )
    assert packet["claim_permissions"]["personal_fact"] is False
    assert packet["claim_permissions"]["unknown"] is True


def test_supported_inference_requires_traceable_basis_and_interpretive_confidence():
    packet = build_confidence_evidence_packet(
        dims(source="high", retrieval="high", memory="high", interpretation="medium", reasoning="medium"),
        evidence(),
        {},
    )
    assert packet["claim_permissions"]["supported_inference"] is True
    assert "supported_inference" in packet["permitted_claim_kinds"]


def test_prediction_never_becomes_fact_permission():
    packet = build_confidence_evidence_packet(
        dims(source="medium", prediction="medium"),
        {"evidence": []},
        {"handled": True, "status": "ok"},
    )
    assert packet["claim_permissions"]["prediction"] is True
    assert packet["governance"]["prediction_must_not_be_presented_as_fact"] is True


def test_missing_evidence_stays_unknown_and_does_not_force_system_labels():
    packet = build_confidence_evidence_packet(
        dims(source="low", retrieval="low", memory="low"),
        {"recall_active": False, "evidence": []},
        {},
    )
    assert packet["claim_permissions"]["unknown"] is True
    assert packet["governance"]["natural_language_over_system_labels"] is True
    assert packet["aggregation"] == "prohibited"
