"""Layer 4 — longitudinal health-history semantic recall.

Expands natural questions about health, medical history, injuries, treatment,
medications and physical/mental-health changes across life. This layer changes
retrieval only; returned evidence remains authoritative and medical inference is
not introduced here.
"""
import re


def install(rhee):
    previous_terms = rhee.expanded_query_terms
    previous_deep = rhee.deep_recall_requested
    previous_exhaustive = rhee.exhaustive_requested
    previous_plan = rhee.plan_recall

    def health_requested(query):
        text = rhee.safe_text(query).lower()
        return bool(re.search(
            r"\b(?:health|health\s+history|medical|medical\s+history|physical\s+health|"
            r"mental\s+health|injur(?:y|ies)|illness(?:es)?|conditions?|diagnos(?:is|es)|"
            r"medications?|meds|treatment|hospital|hospitalisation|rehab|rehabilitation|"
            r"physio|physiotherapy|pain|sleep|fitness|weight|blood\s+pressure)\b", text
        ))

    def health_terms():
        return {
            "health", "health history", "medical", "medical history", "hospital", "hospitalisation",
            "childhood health", "asthma", "eczema", "ventolin", "breathing", "injury", "injuries",
            "diagnosis", "diagnoses", "condition", "treatment", "medication", "medications", "meds",
            "mental health", "physical health", "ptsd", "cptsd", "adhd", "autism", "audhd", "ocpd",
            "anxiety", "depression", "sleep", "blood pressure", "weight", "fitness", "pain", "ankle",
            "achilles", "knee", "calf", "feet", "foot", "back", "shoulder", "tinnitus", "surgery",
            "physio", "physiotherapy", "exercise physiology", "rehab", "rehabilitation", "recovery",
            "dva", "gold card", "accepted conditions", "health memory lock-in", "medical report",
            "terri", "julie", "brenton", "pauline",
        }

    def expanded(query):
        terms = list(previous_terms(query))
        if not health_requested(query):
            return terms
        seen = {rhee.safe_text(term).lower() for term in terms}
        for term in sorted(health_terms()):
            if term not in seen:
                terms.append(term)
                seen.add(term)
        return terms

    def deep(query):
        return health_requested(query) or previous_deep(query)

    def exhaustive(query):
        return health_requested(query) or previous_exhaustive(query)

    def plan(query, today=None):
        result = previous_plan(query, today=today)
        if not health_requested(query):
            return result
        result = dict(result)
        result.update({
            "mode": "investigate",
            "topic_intent": "longitudinal_health_history",
            "raw_candidates": max(int(result.get("raw_candidates", 0)), 300),
            "memory_candidates": max(int(result.get("memory_candidates", 0)), 240),
            "evidence_char_budget": max(int(result.get("evidence_char_budget", 0)), 60000),
            "retrieval_budget_ms": 45000,
            "contradiction_review": True,
            "coverage_review": True,
            "temporal_review": True,
        })
        return result

    rhee.expanded_query_terms = expanded
    rhee.deep_recall_requested = deep
    rhee.exhaustive_requested = exhaustive
    rhee.plan_recall = plan
