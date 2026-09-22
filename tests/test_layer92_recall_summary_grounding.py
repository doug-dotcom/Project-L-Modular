"""Personal facts cannot bypass recall checks by using a narrative block type."""
import json

import pytest

from core.cognition.claim_support import evaluate_claim_support, apply_claim_support_gate
from core.cognition.evidence_evaluation import evaluate_answer


ROWS = [{"source": "raw_catchall:92", "role": "user", "quote_source": "I completed Open Water."}]
FACT = {"kind": "fact", "text": "You reported completing Open Water.",
        "citations": [{"source": "raw_catchall:92", "quote": "I completed Open Water."}]}


class Checker:
    available = True
    model_id = "test"
    provider = "test"

    def __init__(self, assertion=False, omit=False, outage=False):
        self.assertion, self.omit, self.outage = assertion, omit, outage
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        if self.outage:
            raise RuntimeError("checker unavailable")
        candidates = json.loads(request["messages"][-1]["content"])["blocks"]
        verdicts = []
        for candidate in candidates:
            if candidate.get("kind") and self.omit:
                continue
            item = {"block": candidate["block"], "verdict": "supported", "atomicity": "atomic"}
            if candidate.get("kind"):
                item["factual_assertion"] = self.assertion
            verdicts.append(item)
        return {"content": json.dumps({"blocks": verdicts, "conflicts": []})}


def publish(kind, text, checker):
    raw = json.dumps({"blocks": [{"kind": kind, "text": text, "citations": []}, FACT]})
    _, citations = evaluate_answer(raw, ROWS)
    support = evaluate_claim_support(raw, citations, checker)
    reply, audit = evaluate_answer(apply_claim_support_gate(raw, support), ROWS)
    return reply, support, audit


@pytest.mark.parametrize("kind,text", [
    ("conversation", "The records establish all three qualifications and the final dive total."),
    ("inference", "Because you completed 12 dives, I think this was a success."),
    ("unknown", "You completed 12 dives, but I cannot confirm the resort."),
])
def test_mislabelled_personal_assertions_are_withheld_without_losing_cited_fact(kind, text):
    checker = Checker(assertion=True)
    reply, support, audit = publish(kind, text, checker)
    assert text not in reply
    assert FACT["text"] in reply
    assert support["failed_blocks"] == [1]
    assert support["checks"][0]["reason"] == "personal_fact_requires_cited_fact_block"
    assert audit["publication_blocks_withheld"] == 1
    assert len(checker.requests) == 1


@pytest.mark.parametrize("kind,text", [
    ("conversation", "Good morning, Doug."),
    ("unknown", "I cannot establish a final trip total from these excerpts."),
    ("inference", "This seems like a meaningful achievement to you."),
])
def test_nonfactual_language_survives_review(kind, text):
    reply, support, audit = publish(kind, text, Checker(assertion=False))
    assert text in reply
    assert support["failed_blocks"] == []
    assert audit["publication_blocks_withheld"] == 0


@pytest.mark.parametrize("checker", [Checker(assertion="false"), Checker(omit=True), Checker(outage=True)])
def test_unavailable_or_malformed_narrative_review_never_approves_a_recap(checker):
    text = "The records confirm the whole trip history."
    reply, support, audit = publish("conversation", text, checker)
    assert text not in reply
    assert FACT["text"] in reply
    assert support["failed_blocks"] == [1]
    assert support["checks"][0]["reason"] == "narrative_type_check_unavailable"
    assert audit["publication_blocks_withheld"] == 1
