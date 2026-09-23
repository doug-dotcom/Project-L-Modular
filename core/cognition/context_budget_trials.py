"""Layer 99: bounded full-vs-budgeted cognition trials.

This suite tests the Layer 98 model-facing context reduction against a full-packet
control using only public synthetic fixtures. It never reads personal memory,
writes routes, or changes production configuration. Conversation quality remains
human-reviewed; objective cases receive only narrow fixture checks.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import isfinite
from statistics import median
from time import monotonic

from core.cognition.context_budget import build_generation_cognitive_context
from core.cognition.model_independence import build_model_request, invoke_model


VERSION = "layer99-context-budget-trials-1"
VARIANTS = ("full", "budgeted")


def _controller(*, difficulty="low", **needs):
    base = {
        "memory": False,
        "current_evidence": False,
        "external_evidence": False,
        "structured_reasoning": False,
        "longitudinal_reasoning": False,
        "specialist": False,
        "action": False,
    }
    base.update(needs)
    return {"difficulty": difficulty, "needs": base}


def trial_cases():
    inactive_noise = "inactive diagnostic detail " * 160
    return [
        {
            "id": "conversation_small_start",
            "suite": "conversation",
            "prompt": (
                "I have five things to do and feel overwhelmed. Help me choose one small "
                "starting action. Return JSON with reply containing your natural response."
            ),
            "rubric": [
                "Acknowledge the expressed overload without diagnosis",
                "Offer one manageable starting action",
                "Avoid a long list",
            ],
            "evidence": "",
            "evidence_required": False,
            "packet": {
                "engine": "project_l_cognitive_core",
                "version": "13.0",
                "runtime": {"status": "complete", "fallback_used": False},
                "controller": _controller(),
                "route": {
                    "rike": "not_required",
                    "mary": "not_required",
                    "confidence_evidence": "active",
                },
                "guardrails": {"passed": True, "issues": []},
                "confidence_dimensions": {"status": "complete"},
                "confidence_evidence": {"status": "complete"},
                "rike": {"status": "not_required", "detail": inactive_noise},
                "mary": {"active": False, "detail": inactive_noise},
                "working_memory": {"conversation_phase": "current_turn"},
                "model_independence": {"foundation_model_is_replaceable": True},
                "portability": {"status": "available"},
            },
        },
        {
            "id": "recall_exact_source",
            "suite": "recall",
            "prompt": (
                "Using only the supplied fictional evidence, what is the storage locker "
                "code and which source states it? Return JSON with code and source."
            ),
            "expected": {"code": "2719", "source": "raw_catchall:4"},
            "evidence": (
                "SYNTHETIC RHEE EVIDENCE\n"
                'source=raw_catchall:4 quote="The storage locker code is 2719."'
            ),
            "evidence_required": True,
            "packet": {
                "engine": "project_l_cognitive_core",
                "version": "13.0",
                "runtime": {"status": "complete", "fallback_used": False},
                "controller": _controller(
                    difficulty="medium",
                    memory=True,
                    current_evidence=True,
                ),
                "route": {
                    "rike": "not_required",
                    "memory_relevance": "use",
                    "confidence_evidence": "active",
                },
                "guardrails": {"passed": True, "issues": []},
                "confidence_dimensions": {"status": "complete"},
                "confidence_evidence": {"status": "complete", "source": "synthetic"},
                "memory_relevance": {"active": True, "decision": "use"},
                "rike": {"status": "not_required", "detail": inactive_noise},
                "mary": {"active": False, "detail": inactive_noise},
                "working_memory": {"current_goal": "answer from evidence"},
                "model_independence": {"foundation_model_is_replaceable": True},
            },
        },
        {
            "id": "reasoning_latest_departure",
            "suite": "reasoning",
            "prompt": (
                "A fictional workshop starts at 10:00. Travel takes 35 minutes, check-in "
                "must finish 15 minutes before the start, and check-in takes 10 minutes. "
                "Return JSON with departure in HH:MM format."
            ),
            "expected": {"departure": "09:00"},
            "evidence": "",
            "evidence_required": False,
            "packet": {
                "engine": "project_l_cognitive_core",
                "version": "13.0",
                "runtime": {"status": "complete", "fallback_used": False},
                "controller": _controller(
                    difficulty="high",
                    structured_reasoning=True,
                ),
                "route": {
                    "rike": "active",
                    "mary": "not_required",
                    "quinn": "advisory",
                    "confidence_evidence": "active",
                },
                "guardrails": {"passed": True, "issues": []},
                "confidence_dimensions": {"status": "complete"},
                "confidence_evidence": {"status": "complete"},
                "rike": {
                    "status": "complete",
                    "conclusion": "Calculate backwards from required completed check-in.",
                    "uncertainties": [],
                },
                "mary": {"active": False, "detail": inactive_noise},
                "quinn": {"status": "complete", "principles": ["Check constraints in order."]},
                "working_memory": {"current_goal": "solve constrained timing"},
                "model_independence": {"foundation_model_is_replaceable": True},
            },
        },
        {
            "id": "reasoning_causal_boundary",
            "suite": "reasoning",
            "prompt": (
                "Fictional observation: on two days someone slept longer and completed "
                "more tasks. There was no experiment or control for other changes. Return "
                "JSON with cause_established (boolean)."
            ),
            "expected": {"cause_established": False},
            "evidence": "",
            "evidence_required": False,
            "packet": {
                "engine": "project_l_cognitive_core",
                "version": "13.0",
                "runtime": {"status": "complete", "fallback_used": False},
                "controller": _controller(
                    difficulty="high",
                    structured_reasoning=True,
                ),
                "route": {
                    "rike": "active",
                    "mary": "active",
                    "quinn": "advisory",
                    "confidence_evidence": "active",
                },
                "guardrails": {"passed": True, "issues": []},
                "confidence_dimensions": {
                    "status": "complete",
                    "dimensions": {"causal": "low"},
                },
                "confidence_evidence": {"status": "complete"},
                "rike": {
                    "status": "complete",
                    "causal_assessment": {
                        "relationship": "association",
                        "supported_causal_claim": False,
                    },
                },
                "mary": {
                    "active": True,
                    "patterns": [{"status": "candidate", "supporting_episodes": 2}],
                },
                "quinn": {"status": "complete", "principles": ["Do not turn correlation into causation."]},
                "working_memory": {"current_goal": "respect causal boundary"},
                "model_independence": {"foundation_model_is_replaceable": True},
            },
        },
    ]


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def trial_manifest(models, repeats=1):
    if any(not isinstance(m, str) or not m.strip() or len(m) > 100 for m in models):
        raise ValueError("Invalid model identifier")
    if not 1 <= len(models) <= 2 or len(set(models)) != len(models):
        raise ValueError("Choose one or two distinct models")
    if type(repeats) is not int or not 1 <= repeats <= 2:
        raise ValueError("Choose one or two repeats")
    cases = trial_cases()
    fingerprint = sha256(_canonical(cases).encode()).hexdigest()
    return {
        "suite_version": VERSION,
        "case_set_sha256": fingerprint,
        "models": list(models),
        "repeats": repeats,
        "variants": list(VARIANTS),
        "cases_per_model": len(cases),
        "planned_calls": len(cases) * len(VARIANTS) * len(models) * repeats,
        "max_output_tokens_per_call": 1536,
        "mode": "synthetic_context_budget_parity",
        "private_memory_reads": False,
        "memory_writes": False,
        "route_changes": False,
        "automatic_promotion": False,
        "cases": cases,
    }


def build_trial_prompt(case, variant):
    if variant not in VARIANTS:
        raise ValueError("Unknown context variant")
    packet = case["packet"]
    if variant == "budgeted":
        built = build_generation_cognitive_context(
            packet,
            evidence_required=bool(case.get("evidence_required")),
        )
        cognitive_context = built["context"]
        context_receipt = built["receipt"]
    else:
        cognitive_context = _canonical(packet)
        context_receipt = {
            "version": VERSION,
            "mode": "full_control",
            "full_packet_chars": len(cognitive_context),
            "rendered_chars": len(cognitive_context),
            "reduction_chars": 0,
            "required_context_preserved": True,
            "rhee_evidence_modified": False,
        }

    system = (
        "You are L. This is a fictional synthetic evaluation. Return JSON only. "
        "Do not perform external actions. Use supplied evidence when present.\n\n"
    )
    if case.get("evidence"):
        system += "RHEE CONTEXT PACKET:\n" + case["evidence"] + "\n\n"
    system += "COGNITIVE PACKET:\n" + cognitive_context
    return {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": case["prompt"]},
        ],
        "context_receipt": context_receipt,
    }


def grade_trial(case, content):
    try:
        answer = json.loads(content)
    except (TypeError, ValueError):
        return {"status": "failed", "checks": {"json_object": False}}
    if not isinstance(answer, dict):
        return {"status": "failed", "checks": {"json_object": False}}
    if case["suite"] == "conversation":
        valid = isinstance(answer.get("reply"), str) and bool(answer["reply"].strip())
        return {
            "status": "review_required" if valid else "failed",
            "checks": {"nonempty_reply": valid},
            "rubric": case["rubric"],
        }
    checks = {
        key: key in answer and type(answer[key]) is type(value) and answer[key] == value
        for key, value in case["expected"].items()
    }
    return {
        "status": "fixture_checks_passed" if all(checks.values()) else "failed",
        "checks": checks,
    }


def _pair_outcomes(results):
    pairs = []
    keys = sorted({(r["model"], r["case"], r["trial"]) for r in results})
    for model, case_id, trial in keys:
        rows = {
            r["variant"]: r
            for r in results
            if (r["model"], r["case"], r["trial"]) == (model, case_id, trial)
        }
        full, budgeted = rows.get("full"), rows.get("budgeted")
        suite = (full or budgeted or {}).get("suite")
        if not full or not budgeted:
            status = "incomplete"
        elif suite == "conversation":
            status = (
                "review_required"
                if full.get("status") == budgeted.get("status") == "review_required"
                else "failed"
            )
        else:
            status = (
                "objective_parity"
                if full.get("status") == budgeted.get("status") == "fixture_checks_passed"
                else "failed"
            )
        pairs.append({
            "model": model,
            "suite": suite,
            "case": case_id,
            "trial": trial,
            "status": status,
            "full_status": full.get("status") if full else "missing",
            "budgeted_status": budgeted.get("status") if budgeted else "missing",
            "budgeted_context": (budgeted or {}).get("context_receipt", {}),
        })
    return pairs


def run_context_budget_trials(adapters, *, repeats=1, deadline_seconds=300, clock=monotonic):
    adapters = list(adapters)
    models = [adapter.model_id for adapter in adapters]
    manifest = trial_manifest(models, repeats)
    if type(deadline_seconds) not in (int, float) or not 1 <= deadline_seconds <= 900:
        raise ValueError("Deadline must be between 1 and 900 seconds")
    if any(not getattr(a, "available", False) for a in adapters):
        raise RuntimeError("model_adapter_unavailable")

    started = clock()
    results, stopped = [], set()
    for trial in range(1, repeats + 1):
        for case_index, case in enumerate(manifest["cases"]):
            variant_order = VARIANTS if (trial + case_index) % 2 else tuple(reversed(VARIANTS))
            built = {variant: build_trial_prompt(case, variant) for variant in VARIANTS}
            for variant in variant_order:
                prompt = built[variant]
                request = build_model_request(
                    prompt["messages"],
                    purpose="l_context_budget_trial_" + case["suite"],
                    max_output_tokens=1536,
                    temperature=0.3,
                    response_format={"type": "json_object"},
                )
                for adapter in adapters:
                    row = {
                        "model": adapter.model_id,
                        "suite": case["suite"],
                        "case": case["id"],
                        "trial": trial,
                        "variant": variant,
                        "context_receipt": prompt["context_receipt"],
                    }
                    if adapter.model_id in stopped or clock() - started >= deadline_seconds:
                        row.update(
                            status="not_run",
                            reason=(
                                "candidate_stopped"
                                if adapter.model_id in stopped
                                else "deadline"
                            ),
                        )
                        results.append(row)
                        continue
                    call_started = clock()
                    try:
                        response = invoke_model(adapter, request)
                        receipt = response.get("receipt") or {}
                        grade = grade_trial(case, response["content"])
                        row.update(
                            answer=response["content"],
                            receipt=receipt,
                            returned_model=response.get("model_id"),
                            grading=grade,
                            status=grade["status"],
                        )
                        if response.get("model_id") != adapter.model_id:
                            row["model_identity_review"] = (
                                "Returned model differs from requested identifier; "
                                "verify alias/snapshot."
                            )
                            if row["status"] == "fixture_checks_passed":
                                row["status"] = "review_required"
                    except Exception as exc:
                        row.update(status="error", error_type=type(exc).__name__)
                        stopped.add(adapter.model_id)
                    row["elapsed_ms"] = round((clock() - call_started) * 1000, 2)
                    results.append(row)

    pairs = _pair_outcomes(results)
    summaries = []
    for model in models:
        rows = [r for r in results if r["model"] == model]
        pair_rows = [p for p in pairs if p["model"] == model]
        elapsed = [r["elapsed_ms"] for r in rows if "elapsed_ms" in r]
        totals, priced = {}, 0
        for row in rows:
            cost = (row.get("receipt") or {}).get("cost") or {}
            amount = cost.get("amount")
            currency = cost.get("currency")
            basis = cost.get("status")
            if (
                type(amount) in (int, float)
                and isfinite(amount)
                and amount >= 0
                and currency in {"USD", "AUD"}
                and basis in {"estimated_standard_text", "actual"}
            ):
                key = (currency, basis)
                totals[key] = totals.get(key, 0) + amount
                priced += 1
        reductions = [
            p.get("budgeted_context", {}).get("reduction_ratio")
            for p in pair_rows
            if type(p.get("budgeted_context", {}).get("reduction_ratio")) in (int, float)
        ]
        summaries.append({
            "model": model,
            "planned": len(rows),
            "attempted": sum(r["status"] != "not_run" for r in rows),
            "outcomes": dict(Counter(r["status"] for r in rows)),
            "pair_outcomes": dict(Counter(p["status"] for p in pair_rows)),
            "attempt_latency_ms": {
                "observed": len(elapsed),
                "median": median(elapsed) if elapsed else None,
            },
            "budget_reduction_ratio": {
                "observed": len(reductions),
                "median": median(reductions) if reductions else None,
            },
            "recorded_cost": {
                "priced_calls": priced,
                "unpriced_attempts": len(elapsed) - priced,
                "totals": [
                    {"currency": c, "basis": b, "amount": round(a, 8)}
                    for (c, b), a in sorted(totals.items())
                ],
            },
        })

    objective_pairs = [p for p in pairs if p["suite"] != "conversation"]
    conversation_pairs = [p for p in pairs if p["suite"] == "conversation"]
    objective_status = (
        "passed"
        if objective_pairs and all(p["status"] == "objective_parity" for p in objective_pairs)
        else "failed_or_incomplete"
    )
    human_review = bool(conversation_pairs) and all(
        p["status"] == "review_required" for p in conversation_pairs
    )

    return {
        "suite_version": VERSION,
        "case_set_sha256": manifest["case_set_sha256"],
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "mode": manifest["mode"],
        "repeats": repeats,
        "planned_calls": manifest["planned_calls"],
        "objective_parity": objective_status,
        "conversation_review_pending": human_review,
        "certification_status": (
            "review_required"
            if objective_status == "passed" and human_review
            else "failed_or_incomplete"
        ),
        "summaries": summaries,
        "pairs": pairs,
        "results": results,
        "promotion_eligible": False,
        "route_changes": False,
        "limitations": [
            "Public synthetic fixtures; no private memory is read or written.",
            "Objective checks test narrow facts/constraints, not total answer quality.",
            "Conversation pairs require human review and cannot auto-pass.",
            "The trial uses the production Layer 98 context selector but not production retrieval.",
            "No model winner, route change, deployment decision or promotion is automatic.",
            "Recorded provider cost estimates are not invoices; missing costs are not zero.",
        ],
    }
