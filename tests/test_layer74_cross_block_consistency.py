import json
from hashlib import sha256
from pathlib import Path

from core.cognition.claim_support import (
    apply_claim_support_gate,
    evaluate_claim_support,
)
from core.cognition.evidence_evaluation import normalise


ROOT = Path(__file__).resolve().parents[1]


def qhash(text):
    return sha256(normalise(text).encode()).hexdigest()


def fact(text, quote, source, covers=None):
    return {
        "kind": "fact",
        "text": text,
        "citations": [{"source": source, "quote": quote}],
        "covers": covers or [],
    }


def raw_answer(*blocks):
    return json.dumps({"blocks": list(blocks)})


def audit_item(block, quote, source):
    return {
        "block": block,
        "kind": "fact",
        "passed": True,
        "issues": [],
        "citations": [{"source": source, "quote_sha256": qhash(quote)}],
    }


def audit(*items):
    return {"status": "citation_checks_passed", "checks": list(items)}


class FakeAdapter:
    provider = "test"
    model_id = "test-model"
    available = True

    def __init__(self, response):
        self.response = response
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        return {
            "status": "complete",
            "content": json.dumps(self.response),
            "provider": self.provider,
            "model_id": self.model_id,
        }


def two_supported_blocks():
    q1 = "I bought the boat on 18 September."
    q2 = "I decided not to buy the boat on 18 September."
    raw = raw_answer(
        fact("I bought the boat on 18 September.", q1, "raw_catchall:1", ["boat decision"]),
        fact("I did not buy the boat on 18 September.", q2, "raw_catchall:2", ["boat decision"]),
    )
    hard_audit = audit(
        audit_item(1, q1, "raw_catchall:1"),
        audit_item(2, q2, "raw_catchall:2"),
    )
    return raw, hard_audit


def test_layer74_withholds_both_sides_of_cross_block_conflict():
    raw, hard_audit = two_supported_blocks()
    adapter = FakeAdapter({
        "blocks": [
            {
                "block": 1,
                "verdict": "supported",
                "atomicity": "atomic",
                "reason": "Quote supports purchase.",
            },
            {
                "block": 2,
                "verdict": "supported",
                "atomicity": "atomic",
                "reason": "Quote supports non-purchase.",
            },
        ],
        "conflicts": [
            {
                "blocks": [1, 2],
                "type": "contradiction",
                "reason": "Same boat, same date, incompatible purchase status.",
            }
        ],
    })

    support = evaluate_claim_support(raw, hard_audit, adapter)
    gated = json.loads(apply_claim_support_gate(raw, support))

    assert support["status"] == "partial"
    assert support["consistency_status"] == "partial"
    assert support["conflict_blocks"] == [1, 2]
    assert support["failed_blocks"] == [1, 2]
    assert len(support["conflicts"]) == 1
    assert all(block["kind"] == "unknown" for block in gated["blocks"])
    assert all(block["covers"] == [] for block in gated["blocks"])
    assert all("conflicts with this claim" in block["text"] for block in gated["blocks"])


def test_layer74_plan_then_outcome_is_not_automatically_a_conflict():
    q1 = "I planned to buy a boat."
    q2 = "I later decided not to buy a boat."
    raw = raw_answer(
        fact("I planned to buy a boat.", q1, "raw_catchall:1"),
        fact("I later decided not to buy a boat.", q2, "raw_catchall:2"),
    )
    hard_audit = audit(
        audit_item(1, q1, "raw_catchall:1"),
        audit_item(2, q2, "raw_catchall:2"),
    )
    adapter = FakeAdapter({
        "blocks": [
            {"block": 1, "verdict": "supported", "atomicity": "atomic", "reason": "Plan."},
            {"block": 2, "verdict": "supported", "atomicity": "atomic", "reason": "Later outcome."},
        ],
        "conflicts": [],
    })

    support = evaluate_claim_support(raw, hard_audit, adapter)

    assert support["status"] == "passed"
    assert support["consistency_status"] == "passed"
    assert support["conflict_blocks"] == []
    assert apply_claim_support_gate(raw, support) == raw


def test_layer74_different_dated_states_can_both_be_true():
    q1 = "In June I was considering a boat."
    q2 = "In September I stopped looking for a boat."
    raw = raw_answer(
        fact("In June I was considering a boat.", q1, "raw_catchall:1"),
        fact("In September I stopped looking for a boat.", q2, "raw_catchall:2"),
    )
    hard_audit = audit(
        audit_item(1, q1, "raw_catchall:1"),
        audit_item(2, q2, "raw_catchall:2"),
    )
    adapter = FakeAdapter({
        "blocks": [
            {"block": 1, "verdict": "supported", "atomicity": "atomic", "reason": "June state."},
            {"block": 2, "verdict": "supported", "atomicity": "atomic", "reason": "September state."},
        ],
        "conflicts": [],
    })

    support = evaluate_claim_support(raw, hard_audit, adapter)

    assert support["status"] == "passed"
    assert support["conflicts"] == []


def test_layer74_invalid_conflict_references_are_ignored_fail_safely():
    q = "I completed Advanced Open Water."
    raw = raw_answer(fact("I completed Advanced Open Water.", q, "raw_catchall:1"))
    hard_audit = audit(audit_item(1, q, "raw_catchall:1"))
    adapter = FakeAdapter({
        "blocks": [
            {"block": 1, "verdict": "supported", "atomicity": "atomic", "reason": "Supported."}
        ],
        "conflicts": [
            {"blocks": [1, 99], "type": "contradiction", "reason": "Invalid second block."},
            {"blocks": [1, 1], "type": "contradiction", "reason": "Duplicate block."},
            {"blocks": [1, 2], "type": "invented_type", "reason": "Invalid type."},
        ],
    })

    support = evaluate_claim_support(raw, hard_audit, adapter)

    assert support["status"] == "passed"
    assert support["consistency_status"] == "passed"
    assert support["conflicts"] == []
    assert support["conflict_blocks"] == []


def test_layer74_missing_conflicts_field_is_backward_compatible():
    q = "I completed Advanced Open Water."
    raw = raw_answer(fact("I completed Advanced Open Water.", q, "raw_catchall:1"))
    hard_audit = audit(audit_item(1, q, "raw_catchall:1"))
    adapter = FakeAdapter({
        "blocks": [
            {"block": 1, "verdict": "supported", "atomicity": "atomic", "reason": "Supported."}
        ]
    })

    support = evaluate_claim_support(raw, hard_audit, adapter)

    assert support["status"] == "passed"
    assert support["consistency_status"] == "unavailable"
    assert support["failed_blocks"] == []


def test_layer74_checker_contract_is_narrow_about_real_conflicts():
    raw, hard_audit = two_supported_blocks()
    adapter = FakeAdapter({
        "blocks": [
            {"block": 1, "verdict": "supported", "atomicity": "atomic", "reason": "One."},
            {"block": 2, "verdict": "supported", "atomicity": "atomic", "reason": "Two."},
        ],
        "conflicts": [],
    })

    evaluate_claim_support(raw, hard_audit, adapter)
    system = adapter.requests[0]["messages"][0]["content"]

    assert "CROSS-BLOCK CONSISTENCY" in system
    assert "SAME event, proposition and relevant time/scope" in system
    assert "plan/intention followed by a later outcome" in system
    assert "Do not choose which side is true" in system


def test_layer74_live_repair_receives_conflict_receipt():
    source = (ROOT / "api" / "server.py").read_text(encoding="utf-8")

    assert 'cross_block_conflicts = list(first_support.get("conflicts", []))' in source
    assert "Cross-block conflicts requiring reconciliation" in source
    assert "silently pick one" in source
    assert "first_pass_cross_block_conflicts" in source


def test_layer74_answer_contract_and_manifest_include_consistency_gate():
    source = (ROOT / "core" / "cognition" / "evidence_evaluation.py").read_text(
        encoding="utf-8"
    )

    assert "mutually incompatible claims" in source
    assert "Preserve genuine conflicts instead of choosing" in source
    assert '"cross_block_factual_consistency"' in source
