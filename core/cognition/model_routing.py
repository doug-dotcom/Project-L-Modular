"""Operator-reviewed routing backed by completed, bounded evaluation receipts.

The current suite measures evidence answers only. It cannot promote a model for
RIKE, images, reports or ordinary conversation without separate measurements.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from core.cognition.model_independence import create_model_adapter, invoke_model

ROUTE = "l_recall_response"
REQUIRED_CASES = {"source_collision", "documented_change", "absent_fact", "prior_answer_not_proof", "chronology"}


def eligible_report(report, *, now=None):
    try:
        stamp = datetime.fromisoformat(report["executed_at"])
        age = ((now or datetime.now(timezone.utc)) - stamp).total_seconds()
        rows = report["results"]
        expected = {(case, trial) for case in REQUIRED_CASES for trial in (1, 2)}
        actual = {(row["case"], row["trial"]) for row in rows}
        return (report.get("mode") == "model_with_synthetic_evidence" and
                report.get("suite_version") == "stage3-evidence-1" and
                0 <= age <= 30 * 86400 and len(rows) == 10 and actual == expected and
                all(row.get("passed") is True and row.get("receipt", {}).get("status") == "complete"
                    and row["receipt"].get("requested_model") == report["model_id"]
                    and row["receipt"].get("api") == report["api"]
                    and row.get("duration_ms", float("inf")) <= 60000 for row in rows))
    except (KeyError, TypeError, ValueError):
        return False


class MeasuredModelRouter:
    provider = "openai"

    def __init__(self, client, model_id, *, routes_path, api="auto", reasoning_effort="low"):
        self.client = client
        self.model_id = model_id
        self.available = client is not None
        self.default = create_model_adapter(client, model_id, api=api, reasoning_effort=reasoning_effort)
        self.routes = {}
        self.route_report = None
        self.routing_manifest = {"status": "baseline_only", "default_model": model_id, "routes": {}}
        try:
            config = json.loads(Path(routes_path).read_text())
            report = config.get("recall_evaluation", {})
            if config.get("enabled") is True and eligible_report(report):
                selected = report["model_id"]
                self.route_report = report
                self.routes[ROUTE] = create_model_adapter(client, selected, api=report["api"],
                                                          reasoning_effort=report.get("reasoning_effort", "low"))
                self.routing_manifest.update(status="measured_recall_route", routes={ROUTE: {
                    "model_id": selected, "evaluated_at": report["executed_at"],
                    "scope": "bounded synthetic evidence cases; production retrieval not certified"}})
        except (OSError, ValueError, TypeError, KeyError):
            self.routing_manifest["configuration"] = "missing_or_invalid"

    def generate(self, request):
        route = request.get("routing_purpose", request.get("purpose"))
        measured = route in self.routes and eligible_report(self.route_report)
        selected = self.routes[route] if measured else self.default
        result = invoke_model(selected, request)
        result.setdefault("receipt", {})["routing"] = {
            "purpose": route, "reason": "measured_recall_route" if measured else "configured_baseline",
            "fallback_attempted": False,
        }
        return result


def configured_adapter(client, model_id, environ):
    return MeasuredModelRouter(client, model_id,
        routes_path=environ.get("L_MODEL_ROUTES_PATH", str(Path(__file__).resolve().parents[2] / "../configs/model_routes.json")),
        api=environ.get("L_MODEL_API", "auto"), reasoning_effort=environ.get("L_REASONING_EFFORT", "low"))
