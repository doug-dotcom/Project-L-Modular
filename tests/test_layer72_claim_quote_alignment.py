import json
from hashlib import sha256
from pathlib import Path

from core.cognition.claim_support import (
    apply_claim_support_gate,
    build_claim_support_payload,
    evaluate_claim_support,
)
from core.cognition.evidence_evaluation import normalise


ROOT = Path(__file__).resolve().parents[1]


def qhash(text):
    return sha256(normalise(text).encode()).hexdigest()


def raw_answer(*blocks):
    return json.dumps({"blocks": list(blocks)})


def fact(text, quote, source="raw_catchall:1", covers=None):
    return {
        "kind": "fact",
        "text": text,
        "citations": [{"source": source, "quote": quote}],
        "covers": covers or [],
    }


def conversation(text):
    return {
        "kind": "conversation",
        "text": text,
        "citations": [],
        "covers": [],
    }


def audit_item(block, quote, source="raw_catchall:1", passed=True):
    return {
        "block": block,
        "kind": "fact",
        "passed": passed,
        "issues": [] if passed else ["quote_not_in_cited_source"],
        "citations": (
            [{"source": source, "quote_sha256": qhash(quote)}]
            if passed else []
        ),
    }


def audit(*items):
    return {
        "status": "citation_checks_passed",
        "checks": list(items),
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


class UnavailableAdapter:
    provider = "test"
    model_id = "offline"
    available = False


def test_layer72_payload_uses_only_citation_gate_accepted_exact_quotes():
    good_quote = "I completed Advanced Open Water on 11 September."
    bad_quote = "I also mentioned a future trip."
    raw = raw_answer(
        {
            "kind": "fact",
            "text": "Doug completed Advanced Open Water.",
            "citations": [
                {"source": "raw_catchall:1", "quote": good_quote},
                {"source": "raw_catchall:1", "quote": bad_quote},
            ],
            "covers": [],
        },
        conversation("General explanation."),
    )
    payload = build_claim_support_payload(
        raw,
        audit(audit_item(1, good_quote)),
    )

    assert len(payload) == 1
    assert payload[0]["block"] == 1
    assert payload[0]["claim"] == "Doug completed Advanced Open Water."
    assert payload[0]["evidence"] == [
        {"source": "raw_catchall:1", "quote": good_quote}
    ]


def test_layer72_supported_claim_passes_without_rewrite():
    quote = "I completed Advanced Open Water on 11 September."
    raw = raw_answer(fact("I completed Advanced Open Water.", quote))
    adapter = FakeAdapter({
        "blocks": [
            {"block": 1, "verdict": "supported", "reason": "The quote states completion."}
        ]
    })

    support = evaluate_claim_support(
        raw,
        audit(audit_item(1, quote)),
        adapter,
    )

    assert support["status"] == "passed"
    assert support["failed_blocks"] == []
    assert apply_claim_support_gate(raw, support) == raw
    assert adapter.requests[0]["purpose"] == "l_deep_recall_claim_quote_alignment"
    system = adapter.requests[0]["messages"][0]["content"]
    assert "Use ONLY the exact evidence quotes" in system
    assert "Do not use outside knowledge" in system


def test_layer72_partial_claim_is_withheld_as_a_whole_block():
    quote = "I completed Advanced Open Water on 11 September."
    raw = raw_answer(
        fact(
            "I completed Advanced Open Water and immediately became a Divemaster.",
            quote,
            covers=["diving progress"],
        )
    )
    adapter = FakeAdapter({
        "blocks": [
            {
                "block": 1,
                "verdict": "partial",
                "reason": "The quote supports Advanced Open Water but not Divemaster.",
            }
        ]
    })

    support = evaluate_claim_support(raw, audit(audit_item(1, quote)), adapter)
    gated = json.loads(apply_claim_support_gate(raw, support))
    block = gated["blocks"][0]

    assert support["status"] == "partial"
    assert support["failed_blocks"] == [1]
    assert block["kind"] == "unknown"
    assert block["citations"] == []
    assert block["covers"] == []
    assert "supports only part" in block["text"]


def test_layer72_contradicted_claim_gets_specific_withholding_text():
    quote = "I did not buy the boat."
    raw = raw_answer(fact("I bought the boat.", quote))
    adapter = FakeAdapter({
        "blocks": [
            {
                "block": 1,
                "verdict": "contradicted",
                "reason": "The quote explicitly says the boat was not bought.",
            }
        ]
    })

    support = evaluate_claim_support(raw, audit(audit_item(1, quote)), adapter)
    gated = json.loads(apply_claim_support_gate(raw, support))

    assert support["failed_blocks"] == [1]
    assert "conflicts with this claim" in gated["blocks"][0]["text"]


def test_layer72_unvalidated_fact_block_is_not_sent_to_semantic_checker():
    quote = "A quote that failed the hard citation gate."
    raw = raw_answer(fact("A factual claim.", quote))
    adapter = FakeAdapter({"blocks": []})

    support = evaluate_claim_support(
        raw,
        audit(audit_item(1, quote, passed=False)),
        adapter,
    )

    assert support["status"] == "not_required"
    assert support["checked_blocks"] == 0
    assert adapter.requests == []


def test_layer72_checker_outage_does_not_corrupt_or_withhold_existing_hard_gated_answer():
    quote = "I completed Advanced Open Water on 11 September."
    raw = raw_answer(fact("I completed Advanced Open Water.", quote))

    support = evaluate_claim_support(
        raw,
        audit(audit_item(1, quote)),
        UnavailableAdapter(),
    )

    assert support["status"] == "unavailable"
    assert support["independent_truth_certification"] is False
    assert apply_claim_support_gate(raw, support) == raw


def test_layer72_missing_verdict_is_unavailable_not_false_failure():
    quote = "I completed Advanced Open Water on 11 September."
    raw = raw_answer(fact("I completed Advanced Open Water.", quote))
    adapter = FakeAdapter({"blocks": []})

    support = evaluate_claim_support(raw, audit(audit_item(1, quote)), adapter)

    assert support["status"] == "unavailable"
    assert support["failed_blocks"] == []
    assert support["checks"][0]["verdict"] == "unavailable"
    assert apply_claim_support_gate(raw, support) == raw


def test_layer72_live_server_checks_both_first_pass_and_repair():
    source = (ROOT / "api" / "server.py").read_text(encoding="utf-8")

    assert source.count("evaluate_claim_support(") >= 2
    assert source.count("apply_claim_support_gate(") >= 2
    assert "first_pass_claim_support_failures" in source
    assert "Every material factual clause" in source
