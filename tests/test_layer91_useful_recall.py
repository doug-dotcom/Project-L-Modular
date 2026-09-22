"""Recall must expose buried source text and keep publication failures readable."""
import json
from hashlib import sha256

from core.cognition.claim_support import apply_claim_support_gate
from core.cognition.evidence_evaluation import evaluate_answer
from core.cognition.recall_excerpts import recall_windows


QUERY = "What do you remember about my diving trip, certifications and logged dives?"


def test_late_certification_and_dated_total_survive_long_report():
    content = ("Holiday report.\n\n" + "A quiet morning with a restful breakfast. " * 50
               + "\n\nTrip total on 13 September: 10 completed dives.\n\n"
               + "I completed Advanced Open Water and Enriched Air Nitrox.\n\n"
               + "Two more dives are planned tomorrow.\n\n" + "General reflection. " * 60)
    windows = recall_windows(content, QUERY, ["advanced", "nitrox", "completed"], limit=1600)
    visible = "\n".join(text for _, text in windows)
    assert "10 completed dives." in visible
    assert "Enriched Air Nitrox." in visible
    assert sum(len(text) for _, text in windows) <= 1600
    for offset, text in windows:
        assert content[offset:offset + len(text)] == text


def test_raw_and_promoted_recall_use_relevant_windows_with_provenance(monkeypatch):
    from agents.rhee import rhee_v3 as rhee
    monkeypatch.setattr(rhee, "deep_recall_requested", lambda _: True)
    monkeypatch.setattr(rhee, "calculate_raw_score", lambda *_: 10)
    content = "Restful morning. " * 100 + "\n\nI completed my diving certifications."
    raw, promoted = [], []
    rhee.build_raw_recall_packet(QUERY, rows=[{"id": 91, "role": "user", "content": content}], evidence_out=raw)
    rhee.format_memory_packet(QUERY, [{"id": 19, "_table": "memory_general", "raw_id": 91,
        "_source_role": "user", "content": content}], evidence_out=promoted)
    for rows in [raw, promoted]:
        assert any("completed my diving certifications." in r["quote_source"] for r in rows)
        assert all(r["role"] == "user" for r in rows)
    assert promoted[0]["raw_id"] == 91


def test_separate_windows_cannot_validate_a_stitched_quote():
    rows = [{"source": "raw_catchall:91", "role": "user", "quote_source": t}
            for t in ["Completed Open Water.", "Later completed Nitrox."]]
    raw = json.dumps({"blocks": [{"kind": "fact", "text": "Two qualifications.",
        "citations": [{"source": "raw_catchall:91", "quote": "Completed Open Water. Later completed Nitrox."}]}]})
    _, audit = evaluate_answer(raw, rows)
    assert audit["status"] == "blocked"
    assert "quote_not_in_cited_source" in audit["checks"][0]["issues"]


def test_failed_blocks_do_not_swamp_verified_answer_or_erase_audit():
    fact = {"kind": "fact", "text": "Your report records Open Water completion.",
            "citations": [{"source": "raw_catchall:91", "quote": "I completed Open Water."}]}
    raw = json.dumps({"blocks": [fact, {**fact, "text": "Compound claim."},
        {**fact, "citations": []}, {"kind": "unknown", "text": "The final trip total is not established."}]})
    gated = apply_claim_support_gate(raw, {"checks": [{"block": 2, "verdict": "supported", "atomicity": "compound"}]})
    reply, audit = evaluate_answer(gated, [{"source": "raw_catchall:91", "role": "user", "quote_source": "I completed Open Water."}])
    assert "report records Open Water completion" in reply
    assert "final trip total is not established" in reply
    assert "fact block" not in reply and "Compound claim" not in reply
    assert reply.count("Some details could not be verified") == 1
    assert audit["publication_blocks_withheld"] == 2
    assert audit["status"] == "partial"
    assert audit["reply_sha256"] == sha256(reply.encode()).hexdigest()


def test_all_failed_blocks_produce_one_honest_gap():
    raw = json.dumps({"blocks": [{"kind": "fact", "text": "Unsupported history", "citations": []}] * 5})
    reply, audit = evaluate_answer(raw, [])
    assert "Unsupported history" not in reply
    assert reply.count("couldn't verify") == 1
    assert audit["publication_blocks_withheld"] == 5
    assert audit["status"] == "blocked"


def test_repair_receives_original_draft_and_rechecks_split_claims(monkeypatch):
    from api import server
    from types import SimpleNamespace as NS
    from core.cognition.model_independence import OpenAIChatCompletionsAdapter
    quote = "I completed Open Water. I later completed Nitrox."
    def block(text):
        return {"kind": "fact", "text": text, "citations": [{"source": "raw_catchall:91", "quote": quote}]}
    first = json.dumps({"blocks": [block("I completed Open Water and I completed Nitrox.")]})
    fixed = json.dumps({"blocks": [block("I completed Open Water."), block("I later completed Nitrox.")]})
    requests = []
    class Adapter(OpenAIChatCompletionsAdapter):
        def __init__(self):
            client = NS(chat=NS(completions=NS(create=lambda **kwargs: NS(
                id="fixture", model="test", choices=[NS(finish_reason="stop", message=NS(content=self.content))]))))
            super().__init__(client, model_id="test")
        def generate(self, request):
            requests.append(request)
            if request["purpose"] == "l_deep_recall_publication_repair":
                assert request["messages"][-2] == {"role": "assistant", "content": first}
                assert "compound" in request["messages"][-1]["content"]
                self.content = fixed
            elif request["purpose"] == "l_deep_recall_claim_quote_alignment":
                count = len(json.loads(request["messages"][-1]["content"])["blocks"])
                self.content = json.dumps({"blocks": [{"block": n, "verdict": "supported", "atomicity": "compound" if count == 1 else "atomic"} for n in range(1, count + 1)], "conflicts": []})
            else:
                self.content = first
            return super().generate(request)
    monkeypatch.setattr(server, "resolve_model_adapter", lambda: Adapter())
    monkeypatch.setattr(server, "build_rhee_packet", lambda _: {"context": "Evidence", "deep_recall": True,
        "evidence": [{"source": "raw_catchall:91", "role": "user", "quote_source": quote}], "recall_active": True})
    monkeypatch.setattr(server, "route_capability", lambda _: {"handled": False, "status": "not_required"})
    monkeypatch.setattr(server, "run_cognitive_core", lambda *a, **kw: {})
    monkeypatch.setattr(server, "write_raw_catchall", lambda *a, **kw: None)
    monkeypatch.setattr(server, "write_live_short_term", lambda *a: {"saved": False})
    monkeypatch.setattr(server, "run_brain_pipeline", lambda _: None)
    monkeypatch.setattr(server, "voice_enabled", lambda: False)
    result = server.chat(server.ChatRequest(message=QUERY))
    assert "completed Open Water." in result["reply"], {k: v for k, v in result["cognition"]["evidence_evaluation"].items() if "receipt_integrity" in k or "rejection_reason" in k}
    assert "later completed Nitrox." in result["reply"]
    audit = result["cognition"]["evidence_evaluation"]
    assert audit["repair_accepted"] is True
    assert audit["claim_support"]["compound_blocks"] == []
    assert sum(r["purpose"] == "l_deep_recall_publication_repair" for r in requests) == 1
