"""Plan trials by default; --run explicitly makes bounded paid model calls.

python -m scripts.run_model_trials --models MODEL_A MODEL_B --repeats 2
Add --run in the authorised runtime with OPENAI_API_KEY to execute the plan.
Outputs JSON for review. Never modifies routes, tasks or personal memory.
"""
import argparse
import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from core.cognition.model_independence import create_model_adapter
from core.cognition.model_trials import run_model_trials, trial_manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--repeats", type=int, choices=(1, 2, 3), default=2)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    try:
        plan = trial_manifest(args.models, args.repeats)
    except ValueError as exc:
        parser.error(str(exc))
    if not args.run:
        print(json.dumps({"status": "planned_not_executed", **plan}, indent=2))
        return 0
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        parser.error("OPENAI_API_KEY is not configured; no model calls were made.")
    with OpenAI(timeout=45, max_retries=0) as client:
        adapters = [create_model_adapter(client, model, api=os.getenv("L_MODEL_API", "auto")) for model in args.models]
        result = run_model_trials(adapters, repeats=args.repeats)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if any(r["status"] in {"error", "not_run", "failed"} for r in result["results"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
