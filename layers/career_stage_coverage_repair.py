"""Career recall stage-coverage repair.

A broad career query can look well-covered when many Army records are returned,
even while the civilian middle is absent. For career_history only, require
retrieval evidence across distinct career stages and run bounded targeted passes
for stages that are missing. This is retrieval-only: no facts are created and
returned source evidence remains authoritative.
"""

CAREER_STAGES = {
    "military": {"army", "military", "artillery", "kapooka", "puckapunyal", "6rar", "101 battery"},
    "travel_business": {"jetset", "alstonville travel", "travel agency", "owner manager", "travel shop"},
    "hospitality_business": {"hotel richards", "mitchell", "publican", "hotel", "pub"},
    "anz_banking": {"anz", "personal banker", "financial planner associate", "planning forum"},
    "financial_planning_business": {"struthers financial", "capstone", "advice practice", "financial planner", "business owner"},
    "work_endpoint": {"finished work", "medical retirement", "medically retired", "november 2023", "income protection", "disablement"},
}


def install(rhee):
    previous_packet = rhee.build_context_packet

    def evidence_text(items):
        return " ".join(
            (rhee.safe_text(item.get("source")) + " " + rhee.safe_text(item.get("quote_source"))).lower()
            for item in items
        )

    def represented(items):
        text = evidence_text(items)
        return {stage for stage, cues in CAREER_STAGES.items() if any(cue in text for cue in cues)}

    def evidence_key(item):
        return (rhee.safe_text(item.get("source")), rhee.safe_text(item.get("quote_source")))

    def packet(query):
        first = previous_packet(query)
        receipt = dict(first.get("recall_plan") or {})
        if receipt.get("topic_intent") != "career_history" or receipt.get("status") == "needs_clarification":
            return first

        evidence = list(first.get("evidence") or [])
        initial = represented(evidence)
        missing = [stage for stage in CAREER_STAGES if stage not in initial]
        if not missing:
            receipt.update({"career_stage_coverage": "passed", "career_stages": sorted(initial), "career_stages_missing": []})
            first["recall_plan"] = receipt
            return first

        merged = list(evidence)
        seen = {evidence_key(item) for item in merged}
        contexts = []

        # Search each absent career stage independently. The stage vocabulary is
        # intentionally descriptive rather than an answer: Supabase still has to
        # return evidence supporting any employer, role, date or transition.
        for stage in missing:
            cues = " ".join(sorted(CAREER_STAGES[stage]))
            targeted_query = (
                f"{rhee.safe_text(query)} deep recall career stage {stage} {cues} "
                "work memory lock-in pack employment chronology"
            )
            extra = previous_packet(targeted_query)
            for item in list(extra.get("evidence") or []):
                key = evidence_key(item)
                if key not in seen:
                    merged.append(item)
                    seen.add(key)
            extra_context = rhee.safe_text(extra.get("context"))
            if extra_context:
                contexts.append(f"RHEE CAREER STAGE PASS — {stage.upper()}\n{extra_context}")

        final = represented(merged)
        still_missing = [stage for stage in CAREER_STAGES if stage not in final]
        context = rhee.safe_text(first.get("context"))
        if contexts:
            context += "\n\n" + "\n\n".join(contexts)

        output = dict(first)
        output["evidence"] = merged
        output["context"] = context
        output["context_size"] = len(context)
        output["recall_active"] = bool(merged) or bool(first.get("recall_active"))
        receipt.update({
            "career_stage_coverage": "repaired" if len(still_missing) < len(missing) else "incomplete",
            "career_stages_expected": list(CAREER_STAGES),
            "career_stages_initial": sorted(initial),
            "career_stage_targeted_passes": missing,
            "career_stages": sorted(final),
            "career_stages_missing": still_missing,
        })
        output["recall_plan"] = receipt
        return output

    rhee.build_context_packet = packet
