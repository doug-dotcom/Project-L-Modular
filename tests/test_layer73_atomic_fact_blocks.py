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


def raw_fact(text, quote, covers=None):
    return json.dumps({
        "blocks": [{
            "kind": "fact",
            "text": text,
            "citations": [{"source": "raw_catchall:1", "quote": quote}],
            "covers": covers or [],
        }]
    })


def audit(quote):
    return {
        "status": "citation_checks_passed",
        "checks": [{
            "block": 1,
            "kind": "fact",
            "passed": True,
            "issues": [],
            "citations": [{
                "source": "raw_catchall:1",
                "quote_sha256": qhash(quote),
            }],
        }],
    }


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


def test_layer73_supported_compound_fact_is_withheld_until_split():
    quote = "I completed Open Water and later completed Advanced Open Water."
    raw = raw_fact(
        "I completed Open Water and I completed Advanced Open Water.",
        quote,
        covers=["diving progress"],
    )
    adapter = FakeAdapter({
        "blocks": [{
            "block": 1,
            "verdict": "supported",
            "atomicity": "compound",
            "reason": "Two independently verifiable certifications are bundled.",
        }]
    })

    support = evaluate_claim_support(raw, audit(quote), adapter)
    gated = json.loads(apply_claim_support_gate(raw, support))
    block = gated["blocks"][0]

    assert support["status"] == "partial"
    assert support["compound_blocks"] == [1]
    assert support["failed_blocks"] == [1]
    assert support["atomicity_status"] == "partial"
    assert block["kind"] == "unknown"
    assert block["citations"] == []
    assert block["covers"] == []
    assert "independently verifiable claims" in block["text"]


def test_layer73_atomic_single_event_with_multiple_attributes_can_publish():
    quote = "I completed Advanced Open Water on 11 September in Bali."
    raw = raw_fact(
        "I completed Advanced Open Water on 11 September in Bali.",
        quote,
    )
    adapter = FakeAdapter({
        "blocks": [{
            "block": 1,
            "verdict": "supported",
            "atomicity": "atomic",
            "reason": "One certification event with date and place attributes.",
        }]
    })

    support = evaluate_claim_support(raw, audit(quote), adapter)

    assert support["status"] == "passed"
    assert support["compound_blocks"] == []
    assert support["atomicity_status"] == "passed"
    assert apply_claim_support_gate(raw, support) == raw


def test_layer73_semantic_failure_still_takes_precedence_over_atomicity():
    quote = "I completed Open Water."
    raw = raw_fact(
        "I completed Open Water and became a Divemaster.",
        quote,
    )
    adapter = FakeAdapter({
        "blocks": [{
            "block": 1,
            "verdict": "partial",
            "atomicity": "compound",
            "reason": "Only Open Water is supported and two facts are bundled.",
        }]
    })

    support = evaluate_claim_support(raw, audit(quote), adapter)
    gated = json.loads(apply_claim_support_gate(raw, support))

    assert support["failed_blocks"] == [1]
    assert support["compound_blocks"] == [1]
    assert "supports only part" in gated["blocks"][0]["text"]


def test_layer73_missing_atomicity_is_backward_compatible_not_false_failure():
    quote = "I completed Advanced Open Water."
    raw = raw_fact("I completed Advanced Open Water.", quote)
    adapter = FakeAdapter({
        "blocks": [{
            "block": 1,
            "verdict": "supported",
            "reason": "Supported.",
        }]
    })

    support = evaluate_claim_support(raw, audit(quote), adapter)

    assert support["status"] == "passed"
    assert support["atomicity_status"] == "unavailable"
    assert support["failed_blocks"] == []
    assert apply_claim_support_gate(raw, support) == raw


def test_layer73_checker_prompt_defines_atomicity_narrowly():
    quote = "I completed Advanced Open Water on 11 September in Bali."
    raw = raw_fact(
        "I completed Advanced Open Water on 11 September in Bali.",
        quote,
    )
    adapter = FakeAdapter({
        "blocks": [{
            "block": 1,
            "verdict": "supported",
            "atomicity": "atomic",
            "reason": "One event.",
        }]
    })

    evaluate_claim_support(raw, audit(quote), adapter)
    system = adapter.requests[0]["messages"][0]["content"]

    assert "attributes of the same event/entity" in system
    assert "materially independent factual propositions" in system
    assert '"atomicity":"atomic|compound"' in system


def test_layer73_live_repair_includes_compound_atomicity_failures():
    source = (ROOT / "api" / "server.py").read_text(encoding="utf-8")

    assert 'item.get("atomicity") == "compound"' in source
    assert "one independently verifiable proposition" in source
    assert "split materially independent facts into separate blocks" in source


def test_layer73_primary_answer_contract_requests_atomic_fact_blocks():
    source = (ROOT / "core" / "cognition" / "evidence_evaluation.py").read_text(
        encoding="utf-8"
    )

    assert "one independently verifiable proposition" in source
    assert "Split\nmaterially independent facts into separate blocks" in source
    assert '"atomic_fact_block_structure"' in source
