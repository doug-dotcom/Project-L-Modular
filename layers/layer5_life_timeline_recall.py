"""Layer 5 — cross-domain life-timeline semantic recall.

Allows questions such as "what was happening when I was 15?", "tell me about
1998", or "what was my life like in my twenties?" to retrieve across domains
rather than from one topical silo. Retrieval only; evidence remains authoritative.
"""
import re


def install(rhee):
    previous_terms = rhee.expanded_query_terms
    previous_deep = rhee.deep_recall_requested
    previous_exhaustive = rhee.exhaustive_requested
    previous_plan = rhee.plan_recall

    def timeline_requested(query):
        text = rhee.safe_text(query).lower()
        return bool(
            re.search(r"\b(?:life\s+timeline|timeline|life\s+story|life\s+history|my\s+life|what\s+was\s+happening|what\s+was\s+my\s+life\s+like)\b", text)
            or re.search(r"\b(?:when\s+i\s+was|at\s+age|aged)\s+\d{1,2}\b", text)
            or re.search(r"\b(?:in|during|around)\s+(?:19\d{2}|20\d{2})\b", text)
            or re.search(r"\b(?:my\s+)?(?:teens|twenties|thirties|forties|fifties)\b", text)
        )

    def explicit_years(query):
        return {m.group(0) for m in re.finditer(r"\b(?:19\d{2}|20\d{2})\b", rhee.safe_text(query))}

    def explicit_age(query):
        match = re.search(r"\b(?:when\s+i\s+was|at\s+age|aged)\s+(\d{1,2})\b", rhee.safe_text(query).lower())
        return int(match.group(1)) if match else None

    def timeline_terms(query):
        terms = {
            "timeline", "life", "history", "childhood", "school", "family", "friends",
            "relationships", "sport", "hockey", "army", "military", "career", "work",
            "employment", "health", "home", "moved", "travel", "married", "children",
            "recovery", "milestone", "event", "year", "age",
        }
        terms.update(explicit_years(query))
        age = explicit_age(query)
        if age is not None:
            terms.add(str(age))
            # Doug was born in 1978. These are search aliases, not answer facts;
            # evidence returned by Rhee remains authoritative for exact dating.
            approx_year = 1978 + age
            terms.update({str(approx_year - 1), str(approx_year), str(approx_year + 1)})
        return terms

    def expanded(query):
        terms = list(previous_terms(query))
        if not timeline_requested(query):
            return terms
        seen = {rhee.safe_text(term).lower() for term in terms}
        for term in sorted(timeline_terms(query)):
            if term not in seen:
                terms.append(term)
                seen.add(term)
        return terms

    def deep(query):
        return timeline_requested(query) or previous_deep(query)

    def exhaustive(query):
        return timeline_requested(query) or previous_exhaustive(query)

    def plan(query, today=None):
        result = previous_plan(query, today=today)
        if not timeline_requested(query):
            return result
        result = dict(result)
        result.update({
            "mode": "investigate",
            "topic_intent": "cross_domain_life_timeline",
            "raw_candidates": max(int(result.get("raw_candidates", 0)), 320),
            "memory_candidates": max(int(result.get("memory_candidates", 0)), 260),
            "evidence_char_budget": max(int(result.get("evidence_char_budget", 0)), 64000),
            "retrieval_budget_ms": 45000,
            "contradiction_review": True,
            "coverage_review": True,
            "temporal_review": True,
            "cross_domain_review": True,
        })
        years = sorted(explicit_years(query))
        if years:
            result["requested_years"] = years
        age = explicit_age(query)
        if age is not None:
            result["requested_age"] = age
        return result

    rhee.expanded_query_terms = expanded
    rhee.deep_recall_requested = deep
    rhee.exhaustive_requested = exhaustive
    rhee.plan_recall = plan
