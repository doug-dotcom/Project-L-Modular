"""Plan Layer 99 context-budget parity trials by default.

python -m scripts.run_context_budget_trials --models MODEL_A --repeats 1
Add --run in an authorised runtime with OPENAI_API_KEY to execute bounded paid
calls. Outputs JSON for review. Never reads personal memory or changes routes.
"""

import argparse
import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from core.cognition.context_budget_trials import (
    run_context_budget_trials,
    trial_manifest,
)
from core.cognition.model_independence import create_model_adapter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--repeats", type=int, choices=(1, 2), default=1)
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
        adapters = [
            create_model_adapter(
                client,
                model,
                api=os.getenv("L_MODEL_API", "auto"),
            )
            for model in args.models
        ]
        result = run_context_budget_trials(adapters, repeats=args.repeats)

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 1 if any(
        row["status"] in {"error", "not_run", "failed"}
        for row in result["results"]
    ) else 0


if __name__ == "__main__":
    raise SystemExit(main())
