"""Operator command: python -m scripts.run_live_evaluation --repeats 2.

Uses the application's existing OpenAI environment configuration. Makes 5-15
bounded model requests. Does not import the server or read/write personal memory.
"""
import argparse
import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from core.cognition.live_evaluation import run_live_evaluation
from core.cognition.model_independence import create_model_adapter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, choices=(1, 2, 3), default=2)
    args = parser.parse_args()
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        parser.error("The application's OPENAI_API_KEY is not configured.")
    adapter = create_model_adapter(OpenAI(timeout=45, max_retries=0), os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                                   api=os.getenv("L_MODEL_API", "auto"))
    result = run_live_evaluation(adapter, repeats=args.repeats)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["cases_passed"] == result["cases_executed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
