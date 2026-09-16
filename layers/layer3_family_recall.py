"""Layer 3 — family-history semantic recall.

Installed from sitecustomize. This layer changes candidate retrieval only: it
expands natural family-history questions into the relational/family vocabulary
already present in Project L. Returned evidence remains authoritative.
"""
import re


def install(rhee):
    previous_terms = rhee.expanded_query_terms
    previous_deep = rhee.deep_recall_requested
    previous_exhaustive = rhee.exhaustive_requested
    previous_plan = rhee.plan_recall

    def family_requested(query):
        text = rhee.safe_text(query).lower()
        return bool(re.search(
            r"\b(?:family|family\s+history|family\s+background|parents?|mother|father|mum|dad|"
            r"siblings?|brothers?|sisters?|children|kids|grandparents?|childhood\s+home|"
            r"growing\s+up|home\s+life|family\s+events?|family\s+timeline)\b", text
        ))

    def family_terms():
        return {
            "family", "family history", "family background", "parents", "mother", "father",
            "mum", "dad", "brother", "sister", "siblings", "children", "kids", "grandparents",
            "childhood", "growing up", "home", "home life", "family timeline", "born", "birth",
            "hospital", "boarding", "school", "rotary", "family business", "family friend",
            "robert", "bob", "irene", "ken", "allison", "david", "iyla", "ashton", "luella",
            "mehlia", "struthers", "family memory", "childhood timeline", "sibling timeline",
        }

    def expanded(query):
        terms = list(previous_terms(query))
        if not family_requested(query):
            return terms
        seen = {rhee.safe_text(term).lower() for term in terms}
        for term in sorted(family_terms()):
            if term not in seen:
                terms.append(term)
                seen.add(term)
        return terms

    def deep(query):
        return family_requested(query) or previous_deep(query)

    def exhaustive(query):
        return family_requested(query) or previous_exhaustive(query)

    def plan(query, today=None):
        result = previous_plan(query, today=today)
        if not family_requested(query):
            return result
        result = dict(result)
        result.update({
            "mode": "investigate",
            "topic_intent": "family_history",
            "raw_candidates": max(int(result.get("raw_candidates", 0)), 280),
            "memory_candidates": max(int(result.get("memory_candidates", 0)), 230),
            "evidence_char_budget": max(int(result.get("evidence_char_budget", 0)), 58000),
            "retrieval_budget_ms": 45000,
            "contradiction_review": True,
            "coverage_review": True,
        })
        return result

    rhee.expanded_query_terms = expanded
    rhee.deep_recall_requested = deep
    rhee.exhaustive_requested = exhaustive
    rhee.plan_recall = plan

    # Chain later modular retrieval layers from this stable bootstrap point.
    from layers.layer4_health_recall import install as install_health
    install_health(rhee)
    from layers.layer5_life_timeline_recall import install as install_timeline
    install_timeline(rhee)
    from layers.layer6_semantic_query_rewriter import install as install_semantic_rewriter
    install_semantic_rewriter(rhee)
    from layers.layer7_retrieval_escalation import install as install_retrieval_escalation
    install_retrieval_escalation(rhee)
    from layers.layer8_coverage_check import install as install_coverage_check
    install_coverage_check(rhee)
    from layers.layer9_authority_conflict import install as install_authority_conflict
    install_authority_conflict(rhee)
    from layers.layer10_recall_confidence import install as install_recall_confidence
    install_recall_confidence(rhee)
    from layers.late_recall_budget_hotfix import install as install_late_recall_budget_hotfix
    install_late_recall_budget_hotfix(rhee)
    from layers.career_stage_coverage_repair import install as install_career_stage_coverage_repair
    install_career_stage_coverage_repair(rhee)
    from layers.layer11_true_deep_recall import install as install_true_deep_recall
    install_true_deep_recall(rhee)
    from layers.layer12_deep_recall_evidence_breadth import install as install_deep_recall_evidence_breadth
    install_deep_recall_evidence_breadth(rhee)
    from layers.layer13_deep_recall_escalation import install as install_deep_recall_escalation
    install_deep_recall_escalation(rhee)
    from layers.layer14_deep_recall_self_audit import install as install_deep_recall_self_audit
    install_deep_recall_self_audit(rhee)
    from layers.layer15_deep_recall_match_windows import install as install_deep_recall_match_windows
    install_deep_recall_match_windows(rhee)
