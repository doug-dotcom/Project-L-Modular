"""Layer 8 — recall coverage check.

Broad personal-recall answers should not be dominated by one well-indexed slice
of Doug's history. After retrieval, inspect which expected memory neighbourhoods
are represented. If an obvious neighbourhood is absent, perform bounded targeted
passes before the answer is composed. Retrieval only; no facts are created.
"""

DOMAIN_CUES = {
    "family": {"family", "mum", "dad", "mother", "father", "brother", "sister", "parent", "childhood"},
    "school": {"school", "teacher", "grade", "woodlawn", "alstonville", "boarding", "education"},
    "relationships": {"friend", "relationship", "partner", "wife", "fiance", "mate", "married"},
    "military": {"army", "military", "artillery", "kapooka", "puckapunyal", "east timor", "6rar"},
    "career": {"career", "work", "employment", "employer", "anz", "jetset", "publican", "financial planner"},
    "health": {"health", "medical", "hospital", "asthma", "eczema", "injury", "diagnosis", "physio"},
    "sport": {"sport", "hockey", "rugby", "cricket", "gym", "diving", "scuba", "training"},
    "recovery": {"recovery", "sobriety", "sober", "clean", "aa", "na", "step", "rehab"},
}

EXPECTED_BY_INTENT = {
    "cross_domain_life_timeline": {"family", "school", "relationships", "military", "career", "health", "sport"},
    "career_history": {"military", "career"},
    "schooling_history": {"school", "relationships", "sport", "family"},
    "family_history": {"family", "school", "relationships"},
    "relationship_history": {"relationships", "family", "school", "military", "career"},
    "longitudinal_health_history": {"health", "military", "sport", "recovery"},
}


def install(rhee):
    previous_packet = rhee.build_context_packet

    def evidence_text(evidence):
        return " ".join(
            (rhee.safe_text(item.get("source")) + " " + rhee.safe_text(item.get("quote_source"))).lower()
            for item in evidence
        )

    def represented_domains(evidence):
        text = evidence_text(evidence)
        return {name for name, cues in DOMAIN_CUES.items() if any(cue in text for cue in cues)}

    def evidence_key(item):
        return (rhee.safe_text(item.get("source")), rhee.safe_text(item.get("quote_source")))

    def packet(query):
        first = previous_packet(query)
        receipt = dict(first.get("recall_plan") or {})
        intent = receipt.get("topic_intent")
        expected = set(EXPECTED_BY_INTENT.get(intent, set()))
        # Semantic broad recall can also request an explicit coverage review.
        if receipt.get("coverage_review") and not expected:
            expected = {"family", "school", "relationships", "military", "career", "health", "sport"}
        if not expected or receipt.get("status") == "needs_clarification":
            return first

        evidence = list(first.get("evidence") or [])
        represented = represented_domains(evidence)
        missing = sorted(expected - represented)
        if not missing:
            receipt.update({"coverage_check": "passed", "coverage_domains": sorted(represented & expected), "coverage_missing": []})
            first["recall_plan"] = receipt
            return first

        merged = list(evidence)
        seen = {evidence_key(item) for item in merged}
        added_context = []
        # Bound the repair to three absent neighbourhoods per request. This
        # prevents a broad timeline query from exploding into unbounded searches.
        checked = missing[:3]
        for domain in checked:
            cues = " ".join(sorted(DOMAIN_CUES[domain]))
            targeted_query = f"{rhee.safe_text(query)} targeted recall coverage {domain} {cues}"
            extra = previous_packet(targeted_query)
            for item in list(extra.get("evidence") or []):
                key = evidence_key(item)
                if key not in seen:
                    merged.append(item)
                    seen.add(key)
            context = rhee.safe_text(extra.get("context"))
            if context:
                added_context.append(f"RHEE COVERAGE PASS — {domain.upper()}\n{context}")

        final_represented = represented_domains(merged)
        still_missing = sorted(expected - final_represented)
        context = rhee.safe_text(first.get("context"))
        if added_context:
            context += "\n\n" + "\n\n".join(added_context)

        result = dict(first)
        result["evidence"] = merged
        result["context"] = context
        result["context_size"] = len(context)
        result["recall_active"] = bool(merged) or bool(first.get("recall_active"))
        receipt.update({
            "coverage_check": "repaired" if len(still_missing) < len(missing) else "incomplete",
            "coverage_expected": sorted(expected),
            "coverage_initial_missing": missing,
            "coverage_targeted_passes": checked,
            "coverage_domains": sorted(final_represented & expected),
            "coverage_missing": still_missing,
        })
        result["recall_plan"] = receipt
        return result

    rhee.build_context_packet = packet
