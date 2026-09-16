"""Layer 6 — semantic memory-neighbourhood query rewriter.

Adds a general intent-to-neighbourhood pass before lexical retrieval. It does
not manufacture facts: it only adds search vocabulary for concepts implied by
the user's natural phrasing. Returned Project L evidence remains authoritative.
"""
import re


NEIGHBOURHOODS = {
    "military_service": {
        "triggers": r"\b(?:army|military|service|soldier|deployment|east\s+timor|kapooka|artillery)\b",
        "terms": {"army", "military", "service", "soldier", "deployment", "east timor", "kapooka", "puckapunyal", "artillery", "101 battery", "6rar", "ready reserve", "signaller", "fire support", "medallion", "discharge"},
    },
    "recovery_journey": {
        "triggers": r"\b(?:recovery|sobriety|sober|clean|aa|na|steps?|sponsor|meetings?)\b",
        "terms": {"recovery", "sobriety", "clean", "sober", "aa", "na", "alcoholics anonymous", "narcotics anonymous", "step work", "steps", "sponsor", "meeting", "hader", "rehab", "gratitude", "inventory"},
    },
    "sport_activity": {
        "triggers": r"\b(?:sport|sports|hockey|fitness|gym|training|athlete|diving|scuba|skiing)\b",
        "terms": {"sport", "hockey", "masters", "training", "fitness", "gym", "athlete", "team", "game", "diving", "scuba", "padi", "ski", "injury", "performance"},
    },
    "finance_legal": {
        "triggers": r"\b(?:finance|financial|money|super|insurance|tpd|income\s+protection|dva|legal|claim|tax|ato)\b",
        "terms": {"finance", "financial", "money", "super", "superannuation", "insurance", "tpd", "income protection", "dva", "claim", "legal", "solicitor", "tax", "ato", "investment", "portfolio", "zurich", "onepath"},
    },
    "projects_building": {
        "triggers": r"\b(?:project|projects|app|apps|shine|built|building|software|system|systems)\b",
        "terms": {"project", "projects", "app", "apps", "shine", "software", "system", "build", "built", "project l", "fiona", "punt", "travel", "dive", "ski", "translate", "supabase", "railway", "github"},
    },
    "travel_experience": {
        "triggers": r"\b(?:travel|trip|holiday|vacation|bali|overseas|flight|hotel|diving\s+trip)\b",
        "terms": {"travel", "trip", "holiday", "bali", "overseas", "flight", "hotel", "resort", "tulamben", "nusa dua", "diving", "experience", "itinerary"},
    },
}


def install(rhee):
    previous_terms = rhee.expanded_query_terms
    previous_deep = rhee.deep_recall_requested
    previous_plan = rhee.plan_recall

    def neighbourhoods(query):
        text = rhee.safe_text(query).lower()
        return [name for name, cfg in NEIGHBOURHOODS.items() if re.search(cfg["triggers"], text)]

    def expanded(query):
        terms = list(previous_terms(query))
        matched = neighbourhoods(query)
        if not matched:
            return terms
        seen = {rhee.safe_text(term).lower() for term in terms}
        for name in matched:
            for term in sorted(NEIGHBOURHOODS[name]["terms"]):
                if term not in seen:
                    terms.append(term)
                    seen.add(term)
        return terms

    def deep(query):
        # A semantic neighbourhood alone should widen recall when the user is
        # explicitly asking to remember/recall/summarise their own history.
        text = rhee.safe_text(query).lower()
        recall_language = bool(re.search(r"\b(?:recall|remember|what\s+do\s+you\s+know|tell\s+me\s+about|summari[sz]e|history)\b", text))
        return (bool(neighbourhoods(query)) and recall_language) or previous_deep(query)

    def plan(query, today=None):
        result = previous_plan(query, today=today)
        matched = neighbourhoods(query)
        if not matched:
            return result
        result = dict(result)
        result["semantic_neighbourhoods"] = matched
        result["semantic_query_rewrite"] = True
        if deep(query):
            result.update({
                "mode": "investigate",
                "raw_candidates": max(int(result.get("raw_candidates", 0)), 260),
                "memory_candidates": max(int(result.get("memory_candidates", 0)), 220),
                "evidence_char_budget": max(int(result.get("evidence_char_budget", 0)), 56000),
                "retrieval_budget_ms": 45000,
                "coverage_review": True,
                "contradiction_review": True,
            })
        return result

    rhee.expanded_query_terms = expanded
    rhee.deep_recall_requested = deep
    rhee.plan_recall = plan
