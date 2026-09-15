import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Production fail-safe: an optional cognitive layer must never take L offline.
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
            print(
                "COGNITIVE CORE DEGRADED: "
                f"error_type={type(exc).__name__} source={source_file}:{source_line}"
            )
            rike = {
                "engine": "rike", "version": "2.0", "status": "degraded_not_run",
                "confidence": {"level": "low", "score": 0.0,
                    "basis": "Optional cognitive processing degraded; use retrieved evidence only."},
                "lenses": [], "hypotheses": [], "counterfactuals": [],
                "conclusion_change_evidence": [],
                "direct_causal_evidence": {"established": False},
                "causal_assessment": {"relationship": "unknown", "supported_causal_claim": False,
                    "basis": "No structured causal assessment was available.",
                    "limitations": ["Do not infer causation."]},
            }
            return {
                "engine": "project_l_cognitive_core", "version": "14.9-failsafe", "status": "degraded",
                "diagnostic": {"error_type": type(exc).__name__, "source_file": source_file,
                    "source_line": source_line},
                "controller": plan,
                "route": {"rhee": "required" if memory_required else "not_required",
                    "rike": "degraded_not_run", "mary": "degraded_not_run",
                    "quinn": "degraded_not_run", "experience_abstraction": "degraded_not_run"},
                "rike": rike,
                "mary": {"engine": "mary", "active": False, "status": "degraded_not_run"},
                "quinn": {"engine": "quinn", "status": "degraded_not_run", "principles": []},
                "confidence_dimensions": {"status": "degraded", "dimensions": {}},
                "guardrails": {"passed": True, "issues": ["optional_cognitive_layer_degraded"]},
                "working_memory": working, "model_independence": {}, "portability": {},
                "experience_abstraction": {"active": False, "status": "degraded_not_run"},
                "learning": {"status": "not_run"}, "multi_agent": {"status": "degraded"},
                "rhee_recall_preserved": bool((rhee_packet or {}).get("recall_active")),
            }

    _orchestrator.run_cognitive_core = _safe_run_cognitive_core
except Exception:
    pass

# Retrieval intent repair. Rhee's FTS is deliberately lexical, so broad human
# concepts must be expanded before candidate search. This layer handles both
# historical cutoffs ("before 1999") and education/schooling requests.
try:
    import re as _re
    import agents.rhee.rhee_v3 as _rhee

    _original_expanded_query_terms = _rhee.expanded_query_terms
    _original_deep_recall_requested = _rhee.deep_recall_requested
    _original_exhaustive_requested = _rhee.exhaustive_requested
    _original_plan_recall = _rhee.plan_recall

    def _historical_cutoff_year(query):
        text = _rhee.safe_text(query).lower()
        match = _re.search(
            r"\b(?:before|prior\s+to|earlier\s+than|pre[-\s]?)(19\d{2}|20\d{2})\b", text
        )
        return int(match.group(1)) if match else None

    def _schooling_requested(query):
        text = _rhee.safe_text(query).lower()
        return bool(_re.search(
            r"\b(?:schooling|school|schools|schooldays|education|primary\s+school|"
            r"high\s+school|boarding\s+school|teachers?|classmates?|grades?)\b", text
        ))

    def _historical_terms(cutoff):
        cues = {
            "born", "birth", "baby", "child", "childhood", "young", "primary", "school",
            "boarding", "teen", "teenage", "adolescent", "friend", "family", "home", "parents",
            "mum", "dad", "brother", "sister", "sport", "hockey", "army", "military", "enlisted",
            "training", "kapooka", "puckapunyal", "work", "job",
        }
        start = 1970 if cutoff > 1970 else max(1900, cutoff - 30)
        cues.update(str(year) for year in range(start, cutoff))
        return cues

    def _schooling_terms():
        # Names/places here are retrieval aliases already present in Doug's
        # archive. They are not asserted as facts by this layer; retrieved USER
        # evidence still governs the answer.
        return {
            "school", "schooling", "education", "primary", "teacher", "teachers", "grade",
            "class", "classmate", "friends", "boarding", "woodlawn", "alstonville", "casino",
            "st marys", "st mary's", "hsc", "ter", "report card", "rugby", "cricket", "hockey",
            "burns", "whiteside", "smith", "patterson", "wright", "searle", "duckett",
        }

    def _expanded_query_terms_with_intent(query):
        terms = list(_original_expanded_query_terms(query))
        additions = set()
        cutoff = _historical_cutoff_year(query)
        if cutoff is not None:
            additions.update(_historical_terms(cutoff))
        if _schooling_requested(query):
            additions.update(_schooling_terms())
        seen = {_rhee.safe_text(term).lower() for term in terms}
        for term in sorted(additions):
            if term not in seen:
                terms.append(term)
                seen.add(term)
        return terms

    def _deep_recall_with_intent(query):
        return (
            _historical_cutoff_year(query) is not None
            or _schooling_requested(query)
            or _original_deep_recall_requested(query)
        )

    def _exhaustive_with_intent(query):
        return (
            _historical_cutoff_year(query) is not None
            or _schooling_requested(query)
            or _original_exhaustive_requested(query)
        )

    def _plan_recall_with_intent(query, today=None):
        plan = _original_plan_recall(query, today=today)
        cutoff = _historical_cutoff_year(query)
        school = _schooling_requested(query)
        if cutoff is None and not school:
            return plan
        plan = dict(plan)
        plan.update({
            "mode": "investigate",
            "raw_candidates": 300 if cutoff is not None else 220,
            "memory_candidates": 240 if cutoff is not None else 180,
            "evidence_char_budget": 60000 if cutoff is not None else 48000,
            "retrieval_budget_ms": 45000,
            "contradiction_review": True,
        })
        if cutoff is not None:
            plan["historical_cutoff_year"] = cutoff
        if school:
            plan["topic_intent"] = "schooling_history"
        return plan

    _rhee.expanded_query_terms = _expanded_query_terms_with_intent
    _rhee.deep_recall_requested = _deep_recall_with_intent
    _rhee.exhaustive_requested = _exhaustive_with_intent
    _rhee.plan_recall = _plan_recall_with_intent
except Exception:
    pass
