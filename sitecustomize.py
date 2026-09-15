import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Production fail-safe: an optional cognitive layer must never take L offline.
# The strict core remains authoritative when healthy. If it raises, preserve the
# already-retrieved Rhee evidence and let L answer under conservative guardrails.
try:
    import core.cognition.orchestrator as _orchestrator

    _strict_run_cognitive_core = _orchestrator.run_cognitive_core

    def _safe_run_cognitive_core(*args, **kwargs):
        try:
            return _strict_run_cognitive_core(*args, **kwargs)
        except Exception as exc:
            message = args[0] if args else kwargs.get("message", "")
            rhee_packet = args[1] if len(args) > 1 else kwargs.get("rhee_packet", {})
            plan = kwargs.get("cognitive_plan") or _orchestrator.plan_cognition(message)
            working = kwargs.get("working_memory_packet") or {}
            memory_required = bool((plan.get("needs") or {}).get("memory"))
            tb = exc.__traceback__
            while tb and tb.tb_next:
                tb = tb.tb_next
            source_file = Path(tb.tb_frame.f_code.co_filename).name if tb else "unknown"
            source_line = tb.tb_lineno if tb else None
            # No exception text, request text, evidence or credentials are logged.
            print(
                "COGNITIVE CORE DEGRADED: "
                f"error_type={type(exc).__name__} source={source_file}:{source_line}"
            )
            rike = {
                "engine": "rike",
                "version": "2.0",
                "status": "degraded_not_run",
                "confidence": {
                    "level": "low",
                    "score": 0.0,
                    "basis": "Optional cognitive processing degraded; use retrieved evidence only.",
                },
                "lenses": [],
                "hypotheses": [],
                "counterfactuals": [],
                "conclusion_change_evidence": [],
                "direct_causal_evidence": {"established": False},
                "causal_assessment": {
                    "relationship": "unknown",
                    "supported_causal_claim": False,
                    "basis": "No structured causal assessment was available.",
                    "limitations": ["Do not infer causation."],
                },
            }
            return {
                "engine": "project_l_cognitive_core",
                "version": "14.9-failsafe",
                "status": "degraded",
                "diagnostic": {
                    "error_type": type(exc).__name__,
                    "source_file": source_file,
                    "source_line": source_line,
                },
                "controller": plan,
                "route": {
                    "rhee": "required" if memory_required else "not_required",
                    "rike": "degraded_not_run",
                    "mary": "degraded_not_run",
                    "quinn": "degraded_not_run",
                    "experience_abstraction": "degraded_not_run",
                },
                "rike": rike,
                "mary": {"engine": "mary", "active": False, "status": "degraded_not_run"},
                "quinn": {"engine": "quinn", "status": "degraded_not_run", "principles": []},
                "confidence_dimensions": {"status": "degraded", "dimensions": {}},
                "guardrails": {"passed": True, "issues": ["optional_cognitive_layer_degraded"]},
                "working_memory": working,
                "model_independence": {},
                "portability": {},
                "experience_abstraction": {"active": False, "status": "degraded_not_run"},
                "learning": {"status": "not_run"},
                "multi_agent": {"status": "degraded"},
                "rhee_recall_preserved": bool((rhee_packet or {}).get("recall_active")),
            }

    _orchestrator.run_cognitive_core = _safe_run_cognitive_core
except Exception:
    # Never make interpreter startup depend on the fail-safe itself.
    pass
