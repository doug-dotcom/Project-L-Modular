from core.cognition.controller import plan_cognition
from core.cognition.decision_memory import (
    canonical_decision_text,
    decision_recall_requested,
    extract_decision_memory,
)
from core.cognition.memory_governance import build_memory_payload
from memory.promotion.gate import evaluate_promotion


def test_explicit_decision_captures_reason_and_rejected_alternative():
    record = extract_decision_memory(
        "I decided to use option 2 because it is simpler rather than option 1."
    )
    assert record["decision"] == "to use option 2"
    assert record["rationale"] == "it is simpler"
    assert record["rejected_alternatives"] == ["option 1"]
    assert record["rationale_status"] == "explicit"


def test_missing_reason_remains_missing_not_inferred():
    record = extract_decision_memory("We decided to keep Project L private.")
    assert record["decision"] == "to keep Project L private"
    assert record["rationale"] is None
    assert record["rejected_alternatives"] == []
    assert "not recorded" in canonical_decision_text(record)
    assert record["governance"]["infer_missing_rationale"] is False


def test_questions_are_not_recorded_as_new_decisions():
    assert extract_decision_memory("Why did I decide to use option 2?") is None
    assert decision_recall_requested("Why did I decide to use option 2?") is True


def test_decision_recall_forces_memory_retrieval():
    plan = plan_cognition("Why did I choose option 2 instead of option 1?")
    assert plan["problem_type"] == "decision_recall"
    assert plan["needs"]["memory"] is True
    assert plan["needs"]["decision_memory"] is True
    assert plan["signals"]["decision_memory"] is True


def test_governed_long_term_payload_contains_canonical_decision_evidence():
    row = {
        "id": 9001,
        "role": "user",
        "content": "I decided to use Expand because the cost was lower rather than CFS.",
        "created_at": "2026-09-15T00:00:00+00:00",
    }
    promotion = evaluate_promotion(row)
    assert promotion["promote"] is True
    payload, audit = build_memory_payload(row, promotion)
    assert "DECISION MEMORY" in payload["content"]
    assert "Rationale stated at the time: the cost was lower" in payload["content"]
    assert "Rejected alternatives stated at the time: CFS" in payload["content"]
    assert payload["metadata"]["decision_memory"]["decision"] == "to use Expand"
    assert "decision_memory_v1" in payload["processed_by"]
    assert audit["decision_memory"]["rationale_status"] == "explicit"
