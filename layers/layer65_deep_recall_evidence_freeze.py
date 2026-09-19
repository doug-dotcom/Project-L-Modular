"""Layer 65 — Deep Recall final evidence freeze / late-addition reconciliation.

Layer 63 was restored as a final readiness gate, then Layer 64 introduced one more
retrieval pass after it. That creates a general architectural lesson: any layer
that adds evidence after final audits can make coverage, conflicts, attribution
and readiness stale.

This layer marks the end of evidence mutation for the current pipeline and
reconciles the final packet metadata after all retrieval/rescue stages. It does
not launch another search. Any future evidence-adding layer must be installed
BEFORE this freeze or explicitly replace it with a newer final freeze.
Ordinary Recall is unchanged.
"""


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def as_int(value):
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        evidence = list(result.get("evidence") or [])
        plan = dict(result.get("recall_plan") or {})

        # Recompute simple final-state facts that can become stale when Layer 64
        # adds evidence after earlier final receipts.
        sources = []
        seen = set()
        user_sources = 0
        for item in evidence:
            source = rhee.safe_text(item.get("source")).strip()
            if source and source not in seen:
                sources.append(source)
                seen.add(source)
            if rhee.safe_text(item.get("role")).lower() == "user":
                user_sources += 1

        conflict_added = as_int(plan.get("deep_recall_conflict_targeted_added"))
        prior_readiness = rhee.safe_text(
            plan.get("deep_recall_final_readiness_v2", "unknown")
        ).lower()
        prior_missing = list(
            plan.get("deep_recall_final_readiness_v2_missing_stages") or []
        )
        thin_parts = list(plan.get("deep_recall_final_thin_parts") or [])

        # Layer 64 itself is now required before freeze.
        if "conflict_targeted_rescue" not in prior_missing and (
            "deep_recall_conflict_targeted_rescue" not in plan
        ):
            prior_missing.append("conflict_targeted_rescue")

        if prior_missing:
            final_readiness = "engineering_warning"
        elif thin_parts:
            final_readiness = "ready_with_gaps"
        else:
            final_readiness = "ready"

        output = dict(result)
        plan.update({
            "deep_recall_evidence_freeze": "frozen",
            "deep_recall_evidence_freeze_version": 1,
            "deep_recall_evidence_freeze_sources": len(sources),
            "deep_recall_evidence_freeze_user_items": user_sources,
            "deep_recall_evidence_freeze_conflict_rescue_added": conflict_added,
            "deep_recall_evidence_freeze_prior_readiness": prior_readiness,
            "deep_recall_evidence_freeze_final_readiness": final_readiness,
            "deep_recall_evidence_freeze_missing_stages": prior_missing,
            "deep_recall_evidence_freeze_rule":
                "No evidence-adding layer may run after this freeze.",
        })
        output["recall_plan"] = plan

        lines = [
            "DEEP RECALL FINAL EVIDENCE FREEZE",
            f"Final unique sources={len(sources)}; Doug-authored evidence items={user_sources}; "
            f"late conflict-rescue additions={conflict_added}; readiness={final_readiness.upper()}.",
            "Evidence mutation is now CLOSED for this Deep Recall run. Compose from this frozen packet.",
            "This freeze exists so final coverage, conflict, provenance and readiness conclusions refer to the same evidence state that composition sees.",
            "Do not conceptually launch another retrieval pass during composition. If the frozen packet still has a genuine gap, report it with the calibrated gap rules.",
            "Any future engineering layer that adds evidence must be placed before this freeze, and final audits/readiness must be updated to observe it.",
            "The freeze is an engineering boundary, not a claim that the archive contains no additional relevant memory.",
        ]
        if prior_missing:
            lines.append(
                "Pipeline stages missing before freeze: " + ", ".join(prior_missing)
            )

        context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        return output

    rhee.build_context_packet = packet

    from layers.layer66_deep_recall_composition_manifest import install as install_composition_manifest
    install_composition_manifest(rhee)
