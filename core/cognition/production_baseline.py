"""Read-only operational baseline of saved production answers, not an IQ score.

No model calls, task replay, memory promotion or private answer text in output.
Missing telemetry stays unknown, and versions are never pooled as improvement.
"""
from collections import Counter
from datetime import datetime, timezone
from math import ceil, isfinite
from statistics import median

from core.cognition.delivery_integrity import verify_chat_delivery_payload
from core.cognition.answer_provenance import verify_answer_provenance
from core.cognition.durable_tasks import owner_identity


def _object(value):
    return value if isinstance(value, dict) else {}


def _number(value):
    return value if type(value) in (int, float) and isfinite(value) and value >= 0 else None


def _distribution(values):
    values = sorted(v for v in values if v is not None)
    return {"observed": len(values), "median": median(values) if values else None,
            "p95": values[ceil(len(values)*0.95)-1] if values else None}


def _duration(row):
    try:
        start = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00"))
        if start.tzinfo is None or end.tzinfo is None:
            return None
        return _number(round((end-start).total_seconds()*1000))
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def summarise_production_baseline(rows):
    groups = {}
    seen = set()
    duplicates = malformed = 0
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("request_id"), str):
            malformed += 1
            continue
        if row["request_id"] in seen:
            duplicates += 1
            continue
        seen.add(row["request_id"])
        result = _object(row.get("result"))
        cognition = _object(result.get("cognition"))
        version = str(cognition.get("version") or "unknown")[:80]
        group = groups.setdefault(version, [])
        group.append((row, result, cognition))

    summaries = []
    for version, entries in sorted(groups.items()):
        statuses, delivery, runtime, evidence, models, answer_provenance, release_commits = (
            Counter() for _ in range(7)
        )
        latency, model_latency, recall_latency, source_counts = [], [], [], []
        costs = {}
        errors = cost_observed = 0
        for row, result, cognition in entries:
            status = row.get("status")
            statuses[status if status in {"queued", "running", "ready", "failed", "interrupted"} else "unknown"] += 1
            terminal = status in {"ready", "failed", "interrupted"}
            if terminal:
                latency.append(_duration(row))
            errors += int(result.get("error") is True)
            if not result:
                delivery["no_result"] += 1
            else:
                try:
                    check = verify_chat_delivery_payload(result, expected_request_id=row["request_id"])
                    key = "verified" if check.get("valid") and check.get("bound") else (
                        "legacy_unbound" if check.get("valid") else "invalid")
                except (TypeError, ValueError):
                    key = "invalid"
                delivery[key] += 1
                if key == "invalid":
                    cognition = {}  # Do not trust telemetry in a tampered payload.
            trace = _object(cognition.get("runtime"))
            if trace.get("fallback_used") is True:
                runtime["fallback"] += 1
            elif trace.get("status") == "complete" and trace.get("fallback_used") is False:
                runtime["complete"] += 1
            elif trace.get("status") == "not_run":
                runtime["not_run"] += 1
            elif str(cognition.get("version") or "").endswith("-failsafe"):
                runtime["legacy_fallback"] += 1
            else:
                runtime["unknown"] += 1
            audit = _object(cognition.get("evidence_evaluation"))
            evidence[str(audit.get("status") or "unknown")[:80]] += 1
            receipt = _object(cognition.get("model_receipt"))
            models[str(receipt.get("model_id") or "unknown")[:80]] += 1
            model_latency.append(_number(receipt.get("duration_ms")))

            answer_receipt = _object(cognition.get("answer_provenance"))
            if not answer_receipt:
                answer_provenance["missing"] += 1
            else:
                answer_check = verify_answer_provenance(
                    answer_receipt,
                    request_id=row["request_id"],
                    final_reply=result.get("reply") if isinstance(result.get("reply"), str) else None,
                    release_provenance=_object(cognition.get("release_provenance")),
                    model_receipt=receipt,
                    context_budget=_object(cognition.get("context_budget")),
                    assistant_persistence=_object(cognition.get("assistant_persistence")),
                )
                if not answer_check.get("valid"):
                    answer_provenance["invalid"] += 1
                elif answer_check.get("verified_production"):
                    answer_provenance["verified_production"] += 1
                    commit = str(answer_check.get("release_commit_sha") or "")
                    if commit:
                        release_commits[commit] += 1
                else:
                    answer_provenance["valid_unverified_runtime"] += 1
            recall = _object(cognition.get("recall_plan"))
            recall_latency.append(_number(recall.get("latency_ms")))
            source_counts.append(_number(recall.get("source_count")))
            cost = _object(receipt.get("cost"))
            amount = _number(cost.get("amount"))
            currency, basis = cost.get("currency"), cost.get("status")
            if amount is not None and currency in {"USD", "AUD"} and basis in {"estimated_standard_text", "actual"}:
                key = (currency, basis)
                costs[key] = costs.get(key, 0) + amount
                cost_observed += 1
        summaries.append({
            "cognition_version": version, "tasks": len(entries), "task_status": dict(statuses),
            "error_results": errors, "delivery_integrity": dict(delivery), "runtime": dict(runtime),
            "evidence_audit_status": dict(evidence), "models": dict(models),
            "answer_provenance": dict(answer_provenance),
            "release_commits": dict(release_commits),
            "task_elapsed_ms": _distribution(latency), "response_model_ms": _distribution(model_latency),
            "recall_ms": _distribution(recall_latency), "retrieved_sources": _distribution(source_counts),
            "response_model_cost": {"observed": cost_observed, "missing": len(entries)-cost_observed,
                "totals": [{"currency": currency, "basis": basis, "amount": round(amount, 8)}
                           for (currency, basis), amount in sorted(costs.items())]},
        })
    return {
        "version": "1.0", "mode": "saved_production_operational_baseline",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tasks_observed": len(seen), "duplicate_rows_ignored": duplicates, "malformed_rows_ignored": malformed,
        "status": "observed" if seen else "no_data", "cohorts": summaries,
        "answer_quality": {"status": "not_scored", "score": None,
            "required_review": ["factual_support", "appropriate_abstention", "corrections_and_chronology",
                                "usefulness_and_behaviour", "planning", "learning_from_outcomes"]},
        "limitations": [
            "Operational receipts do not establish factual correctness or intelligence.",
            "Historical samples are not matched tasks and cannot establish causal improvement.",
            "Task elapsed time includes queueing and result persistence, not just reasoning.",
            "Recorded response-model costs exclude other model calls and infrastructure; estimates are not invoices.",
            "Missing or legacy telemetry is unknown, never a pass or zero cost.",
            "Release-commit cohorts describe recorded provenance only; they do not establish causal quality differences.",
        ],
    }


def load_production_baseline(client, recovery_token, limit=50):
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Choose between 1 and 100 tasks")
    user_id, owner_hash = owner_identity(recovery_token)
    if client is None:
        raise RuntimeError("database_unavailable")
    rows = (client.table("l_chat_tasks")
            .select("request_id,created_at,updated_at,status,result")
            .eq("user_id", user_id).eq("owner_hash", owner_hash)
            .order("created_at", desc=True).limit(limit).execute().data)
    if not isinstance(rows, list):
        raise RuntimeError("invalid_database_response")
    report = summarise_production_baseline(rows)
    report["sample"] = {"scope": "recovery_token_owner", "order": "newest_first", "limit": limit}
    return report
