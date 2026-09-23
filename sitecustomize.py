import sys
from pathlib import Path

ROOT = Path(r"C:\Shine_L")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Cognitive fail-safe lives in core.cognition.runtime_safety so every entrypoint uses it.

# Retrieval intent repair. Rhee's FTS is deliberately lexical, so broad human
# concepts are expanded before candidate search. This layer handles historical
# cutoffs, schooling/education, and career/employment history.
#
# sitecustomize is also imported by Python during early venv/pip startup, before
# Project L's pinned dependencies are necessarily available. Dependent recall
# layers must not run unless the Rhee bootstrap import actually succeeded.
_rhee = None
_re = None
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

    def _career_requested(query):
        text = _rhee.safe_text(query).lower()
        return bool(_re.search(
            r"\b(?:career|careers|working\s+career|work\s+history|employment|employment\s+history|"
            r"working\s+life|professional\s+life|professional\s+history|jobs?|employers?|occupations?)\b",
            text,
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
        return {
            "school", "schooling", "education", "primary", "teacher", "teachers", "grade",
            "class", "classmate", "friends", "boarding", "woodlawn", "alstonville", "casino",
            "st marys", "st mary's", "hsc", "ter", "report card", "rugby", "cricket", "hockey",
            "burns", "whiteside", "smith", "patterson", "wright", "searle", "duckett",
        }

    def _career_terms():
        return {
            "work", "working", "career", "employment", "employer", "job", "occupation",
            "professional", "role", "position", "army", "military", "artillery", "kapooka",
            "puckapunyal", "east timor", "ready reserve", "101 battery", "6rar", "signaller",
            "fire support", "soldiers medallion", "jetset", "travel agency", "owner", "manager",
            "hotel richards", "mitchell", "publican", "anz", "personal banker", "financial planner",
            "financial planning", "adviser", "banking", "business", "promotion", "retired",
            "disablement", "income protection", "work memory lock-in", "work history",
        }

    def _expanded_query_terms_with_intent(query):
        terms = list(_original_expanded_query_terms(query))
        additions = set()
        cutoff = _historical_cutoff_year(query)
        if cutoff is not None:
            additions.update(_historical_terms(cutoff))
        if _schooling_requested(query):
            additions.update(_schooling_terms())
        if _career_requested(query):
            additions.update(_career_terms())
        seen = {_rhee.safe_text(term).lower() for term in terms}
        for term in sorted(additions):
            if term not in seen:
                terms.append(term)
                seen.add(term)
        return terms

    def _deep_recall_with_intent(query):
        return (_historical_cutoff_year(query) is not None or _schooling_requested(query)
                or _career_requested(query) or _original_deep_recall_requested(query))

    def _exhaustive_with_intent(query):
        return (_historical_cutoff_year(query) is not None or _schooling_requested(query)
                or _career_requested(query) or _original_exhaustive_requested(query))

    def _plan_recall_with_intent(query, today=None):
        plan = _original_plan_recall(query, today=today)
        cutoff = _historical_cutoff_year(query)
        school = _schooling_requested(query)
        career = _career_requested(query)
        if cutoff is None and not school and not career:
            return plan
        plan = dict(plan)
        broad_topic = school or career
        plan.update({
            "mode": "investigate",
            "raw_candidates": 300 if cutoff is not None else (260 if career else 220),
            "memory_candidates": 240 if cutoff is not None else (220 if career else 180),
            "evidence_char_budget": 60000 if cutoff is not None else (56000 if career else 48000),
            "retrieval_budget_ms": 45000,
            "contradiction_review": True,
        })
        if cutoff is not None:
            plan["historical_cutoff_year"] = cutoff
        if school:
            plan["topic_intent"] = "schooling_history"
        if career:
            plan["topic_intent"] = "career_history"
        if broad_topic:
            plan["coverage_review"] = True
        return plan

    _rhee.expanded_query_terms = _expanded_query_terms_with_intent
    _rhee.deep_recall_requested = _deep_recall_with_intent
    _rhee.exhaustive_requested = _exhaustive_with_intent
    _rhee.plan_recall = _plan_recall_with_intent
except Exception:
    _rhee = None
    _re = None

# Layer 2: relationship recall. Natural questions about "my relationships",
# "people in my life", friends, partners or relationship history should search
# the full relational neighbourhood instead of depending on one literal noun.
try:
    if _rhee is None or _re is None:
        raise RuntimeError("rhee_bootstrap_unavailable")
    _layer2_terms_before = _rhee.expanded_query_terms
    _layer2_deep_before = _rhee.deep_recall_requested
    _layer2_exhaustive_before = _rhee.exhaustive_requested
    _layer2_plan_before = _rhee.plan_recall

    def _relationship_requested(query):
        text = _rhee.safe_text(query).lower()
        return bool(_re.search(
            r"\b(?:relationship|relationships|relationship\s+history|people\s+in\s+my\s+life|"
            r"friends?|friendships?|best\s+mate|mates?|partners?|partner|girlfriends?|boyfriends?|"
            r"wife|wives|husband|fianc[eé]e?|ex(?:es)?|dating|romantic|social\s+circle)\b", text
        ))

    def _relationship_terms():
        return {
            "relationship", "relationships", "friend", "friends", "friendship", "mate", "mates",
            "best mate", "partner", "girlfriend", "wife", "fiancee", "ex", "dating", "romantic",
            "family friend", "childhood friend", "school friend", "army mate", "support", "trust",
            "connection", "history", "met", "known", "lifelong", "married", "engaged", "separated",
            "steven", "steve", "pampel", "wayne", "ratley", "lyndal", "tamara", "leah", "cass",
            "cassandra", "scott", "luke", "shane", "neil", "brad", "ben", "mark", "birdy",
            "relationship memory lock-in", "canonical relationship", "relationship profile",
        }

    def _expanded_query_terms_layer2(query):
        terms = list(_layer2_terms_before(query))
        if not _relationship_requested(query):
            return terms
        seen = {_rhee.safe_text(term).lower() for term in terms}
        for term in sorted(_relationship_terms()):
            if term not in seen:
                terms.append(term)
                seen.add(term)
        return terms

    def _deep_recall_layer2(query):
        return _relationship_requested(query) or _layer2_deep_before(query)

    def _exhaustive_layer2(query):
        return _relationship_requested(query) or _layer2_exhaustive_before(query)

    def _plan_recall_layer2(query, today=None):
        plan = _layer2_plan_before(query, today=today)
        if not _relationship_requested(query):
            return plan
        plan = dict(plan)
        plan.update({
            "mode": "investigate",
            "topic_intent": "relationship_history",
            "raw_candidates": max(int(plan.get("raw_candidates", 0)), 260),
            "memory_candidates": max(int(plan.get("memory_candidates", 0)), 220),
            "evidence_char_budget": max(int(plan.get("evidence_char_budget", 0)), 56000),
            "retrieval_budget_ms": 45000,
            "contradiction_review": True,
            "coverage_review": True,
        })
        return plan

    _rhee.expanded_query_terms = _expanded_query_terms_layer2
    _rhee.deep_recall_requested = _deep_recall_layer2
    _rhee.exhaustive_requested = _exhaustive_layer2
    _rhee.plan_recall = _plan_recall_layer2
except Exception:
    pass

# Layer 3: family-history recall is kept in its own module so subsequent recall
# layers can remain modular rather than making this startup shim indefinitely larger.
if _rhee is not None:
    try:
        from layers.layer3_family_recall import install as _install_layer3_family
        _install_layer3_family(_rhee)
    except Exception as _layer3_exc:
        _tb = _layer3_exc.__traceback__
        while _tb and _tb.tb_next:
            _tb = _tb.tb_next
        _source_file = Path(_tb.tb_frame.f_code.co_filename).name if _tb else "unknown"
        _source_line = _tb.tb_lineno if _tb else None
        print(
            "RECALL LAYER INSTALL DEGRADED: "
            f"error_type={type(_layer3_exc).__name__} "
            f"source={_source_file}:{_source_line} "
            f"detail={str(_layer3_exc)[:160]}"
        )
