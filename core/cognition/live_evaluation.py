"""Run bounded model trials through the production evidence contract.

Synthetic fixtures: no personal memory reads, writes, tools or task promotion.
Unlike Phase 7 this invokes the configured model. Results describe these cases
only and never certify all of L's behaviour.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from time import monotonic

from core.cognition.evidence_evaluation import evidence_prompt, evaluate_answer
from core.cognition.model_independence import build_model_request, invoke_model


def live_cases() -> list[dict]:
    rows = [
        {"source": "memory_project_l:31", "role": "user", "quote_source": "I learn best when you explain the purpose before the details."},
        {"source": "raw_catchall:31", "role": "user", "quote_source": "The garden gate is painted green."},
        {"source": "memory_project_l:42", "role": "user", "quote_source": "I once thought amends meant an apology. Now I see them as changed behaviour every day."},
    ]
    return [
        {"id": "source_collision", "question": "Recall my learning preference. Cite the exact record, including its table.", "evidence": rows, "source": "memory_project_l:31", "words": ["purpose"]},
        {"id": "documented_change", "question": "Recall how my understanding of amends changed. Show the supporting passage.", "evidence": rows, "source": "memory_project_l:42", "words": ["apology", "behaviour"]},
        {"id": "absent_fact", "question": "Recall my first car's registration number. Admit when no supporting evidence is available.", "evidence": rows, "kind": "unknown"},
        {"id": "prior_answer_not_proof", "question": "Did I change my sobriety date? Only answer as fact with independent evidence; otherwise mark it unknown.", "evidence": [{"source": "raw_catchall:80", "role": "assistant", "quote_source": "You changed your sobriety date."}], "kind": "unknown"},
        {"id": "chronology", "question": "Fictional exercise: a report says launch day is 3 September 2026. Its timestamp is 2 September 2026 19:03 UTC. Convert it to Brisbane UTC+10. Are they consistent? Include the local date and time using 05:03.", "evidence": [], "words": ["3 September", "05:03"]},
    ]


def run_live_evaluation(adapter, *, repeats: int = 2) -> dict:
    if not 1 <= repeats <= 3:
        raise ValueError("repeats_must_be_1_to_3")
    if not getattr(adapter, "available", False):
        raise RuntimeError("model_adapter_unavailable")
    results = []
    for case in live_cases():
        for trial in range(1, repeats + 1):
            start = monotonic()
            row = {"case": case["id"], "trial": trial, "passed": False}
            try:
                response = invoke_model(adapter, build_model_request(
                    [{"role": "system", "content": "You are L. These are fictional evaluation records.\n" + evidence_prompt(case["evidence"])},
                     {"role": "user", "content": case["question"]}],
                    purpose="l_live_evaluation", temperature=0.3,
                    max_output_tokens=1000, response_format={"type": "json_object"},
                ))
                reply, audit = evaluate_answer(response["content"], case["evidence"], model_id=response["model_id"])
                blocks = json.loads(response["content"]).get("blocks", [])
                checks = {"citation_integrity": audit["status"] in {"citation_checks_passed", "no_citations_to_check"}}
                if "source" in case:
                    checks["expected_source"] = any(c.get("source") == case["source"] for b in blocks for c in b.get("citations", []))
                if "kind" in case:
                    checks["admits_unknown"] = any(b.get("kind") == case["kind"] for b in blocks) and not any(b.get("kind") == "fact" for b in blocks)
                if "words" in case:
                    answer_text = " ".join(b.get("text", "") for b in blocks).lower()
                    checks["expected_answer_terms"] = all(word.lower() in answer_text for word in case["words"])
                row.update(passed=all(checks.values()), checks=checks, reply=reply, audit=audit)
            except Exception as exc:
                row["error"] = type(exc).__name__
            row["duration_ms"] = round((monotonic() - start) * 1000)
            results.append(row)
    return {"version": "1.0", "executed_at": datetime.now(timezone.utc).isoformat(),
            "model_id": adapter.model_id, "provider": adapter.provider,
            "mode": "model_with_synthetic_evidence", "repeats": repeats,
            "cases_executed": len(results), "cases_passed": sum(r["passed"] for r in results),
            "limitations": ["No production retrieval or database writes", "Answer-term checks are not a semantic judge", "No full-system certification"],
            "results": results}
