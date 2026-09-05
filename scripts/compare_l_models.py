"""Operator-only, bounded trials: python -m scripts.compare_l_models.

Uses the existing provider key in the service. No database access, connected
actions, new credentials or private memory. Never changes production routing.
One run: four models, ten requests each, 4096 output tokens/request, no retries.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
from statistics import median

from openai import OpenAI
from core.cognition.live_evaluation import run_live_evaluation
from core.cognition.model_independence import create_model_adapter
from core.cognition.model_routing import eligible_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--repeats", type=int, choices=(1, 2), default=2)
    args = parser.parse_args()
    models = list(dict.fromkeys([os.getenv("OPENAI_MODEL", "gpt-4o-mini"), "gpt-5.6-terra", "gpt-5.6-sol", "gpt-6-astra"]))
    def trial(model):
        with OpenAI(timeout=45, max_retries=0) as client:
            return run_live_evaluation(create_model_adapter(client, model), repeats=args.repeats)
    with ThreadPoolExecutor(max_workers=4) as pool:
        reports = list(pool.map(trial, models))
    for report in reports:
        rows = report["results"]
        receipts = [r.get("receipt", {}) for r in rows]
        summary = {"model": report["model_id"], "api": report["api"],
                   "passed": report["cases_passed"], "executed": report["cases_executed"],
                   "eligible_for_recall": eligible_report(report),
                   "median_ms": median(r["duration_ms"] for r in rows),
                   "total_input_tokens": sum(r.get("usage", {}).get("input_tokens") or 0 for r in receipts),
                   "total_output_tokens": sum(r.get("usage", {}).get("output_tokens") or 0 for r in receipts),
                   "usage_complete": len(receipts) == len(rows) and all(r.get("usage", {}).get("input_tokens") is not None for r in receipts),
                   "estimated_cost_usd": (round(sum(r["cost"]["amount"] for r in receipts), 6)
                                          if all(r.get("cost", {}).get("amount") is not None for r in receipts) else None),
                   "executed_at": report["executed_at"],
                   "errors": [r.get("error") for r in rows if r.get("error")]}
        print("L_MODEL_TRIAL " + json.dumps(summary, separators=(",", ":")), flush=True)
        for row in rows:
            case = {k: row.get(k) for k in ("case", "trial", "passed", "checks", "duration_ms", "receipt", "error")}
            print("L_MODEL_CASE " + json.dumps({"model": report["model_id"], **case}, separators=(",", ":")), flush=True)
    if args.output:
        args.output.write_text(json.dumps({"reports": reports}, indent=2))
    # Candidate failure must not prevent L's existing model from starting.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
