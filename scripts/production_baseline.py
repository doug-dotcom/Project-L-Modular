"""Summarise up to 100 saved tasks without invoking L or changing memory.

Usage: python -m scripts.production_baseline --input /private/task-export.json

For SQL exports select request_id, created_at, updated_at, status and
result::text AS result_json. Keeping the payload as text prevents intermediaries
normalising 0.0 to 0 before its delivery hash is verified. Never commit exports.
Output is aggregate operational telemetry, not an answer-quality score.
"""
import argparse
import json
from pathlib import Path

from core.cognition.production_baseline import summarise_production_baseline


def parse_task_export(text):
    rows = json.loads(text)
    if not isinstance(rows, list) or len(rows) > 100:
        raise ValueError("Expected a list of at most 100 tasks")
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each task must be an object")
        if "result_json" in row:
            row["result"] = json.loads(row.pop("result_json") or "null")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()
    try:
        rows = parse_task_export(args.input.read_text())
        report = summarise_production_baseline(rows)
    except (OSError, ValueError, TypeError):
        parser.error("Unable to read a valid task export; private input was not logged.")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
