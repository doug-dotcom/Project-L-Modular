"""Fail open to evidence-only conversation, with bounded runtime diagnostics.

No exception messages, traceback source lines, locals or request text belong in
these receipts. The boundary is explicit rather than dependent on site startup.
"""
from __future__ import annotations

from functools import wraps
from inspect import signature
import logging
from pathlib import Path
import re
from time import perf_counter


CORE_VERSION = "14.10"
LOG = logging.getLogger(__name__)


def _identifier(value: str) -> str:
    return value if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]{0,95}", value) else "unknown"


def safe_diagnostic(exc: Exception) -> dict:
    tb = exc.__traceback__
    while tb and tb.tb_next:
        tb = tb.tb_next
    code = tb.tb_frame.f_code if tb else None
    return {
        "error_type": _identifier(type(exc).__name__),
        "source_file": _identifier(Path(code.co_filename).name) if code else "unknown",
        "source_line": tb.tb_lineno if tb else None,
        "source_function": _identifier(code.co_name) if code else "unknown",
    }


def _fallback(arguments: dict, diagnostic: dict) -> dict:
    # A supplied controller plan is already known. Only plan locally if needed;
    # never retry model calls, retrieval, writes or capability actions here.
    plan = arguments.get("cognitive_plan")
    if not isinstance(plan, dict):
        try:
            from core.cognition.controller import plan_cognition
            plan = plan_cognition(arguments.get("message", ""))
        except Exception:
            plan = {}
    rhee = arguments.get("rhee_packet") or {}
    working = arguments.get("working_memory_packet") or {}
    needs = plan.get("needs") or {}
    return {
        "engine": "project_l_cognitive_core", "version": CORE_VERSION + "-failsafe",
        "status": "degraded", "diagnostic": diagnostic, "controller": plan,
        "route": {
            "rhee": "required" if needs.get("memory") else "not_required",
            **{name: "degraded_not_run" for name in (
                "rike", "mary", "quinn", "experience_abstraction")},
        },
        "rike": {
            "engine": "rike", "version": "2.0", "status": "degraded_not_run",
            "confidence": {"level": "low", "score": 0.0,
                "basis": "Optional cognitive processing degraded; use retrieved evidence only."},
            "lenses": [], "hypotheses": [], "counterfactuals": [],
            "conclusion_change_evidence": [],
            "direct_causal_evidence": {"established": False},
            "causal_assessment": {"relationship": "unknown", "supported_causal_claim": False,
                "basis": "No structured causal assessment was available.",
                "limitations": ["Do not infer causation."]},
        },
        "mary": {"engine": "mary", "active": False, "status": "degraded_not_run"},
        "quinn": {"engine": "quinn", "status": "degraded_not_run", "principles": []},
        "confidence_dimensions": {"status": "degraded", "dimensions": {}},
        "guardrails": {"passed": False, "issues": ["optional_cognitive_layer_degraded"]},
        "working_memory": working, "model_independence": {}, "portability": {},
        "experience_abstraction": {"active": False, "status": "degraded_not_run"},
        "learning": {"status": "not_run"}, "multi_agent": {"status": "degraded"},
        "rhee_recall_preserved": bool(rhee.get("recall_active")),
    }


def cognitive_failsafe(run):
    contract = signature(run)

    @wraps(run)
    def guarded(*args, **kwargs):
        # Invalid calls are programming errors, not optional stage failures.
        arguments = contract.bind(*args, **kwargs).arguments
        started = perf_counter()
        diagnostic = {}
        try:
            packet = run(*args, **kwargs)
        except Exception as exc:
            diagnostic = safe_diagnostic(exc)
            LOG.warning(
                "COGNITIVE CORE DEGRADED: error_type=%s source=%s:%s function=%s",
                diagnostic["error_type"], diagnostic["source_file"],
                diagnostic["source_line"], diagnostic["source_function"],
            )
            packet = _fallback(arguments, diagnostic)
        packet["runtime"] = {
            "status": "degraded" if diagnostic else "complete",
            "fallback_used": bool(diagnostic),
            "elapsed_ms": round((perf_counter() - started) * 1000, 2),
            "diagnostic": diagnostic,
        }
        return packet

    return guarded
