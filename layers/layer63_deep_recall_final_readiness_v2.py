"""Layer 63 — Deep Recall final readiness gate v2.

Layer 50 was deliberately the final answer-readiness gate at the time it was
created. Layers 51-62 subsequently added assertion, plan/outcome, polarity,
speaker, number/unit, response hygiene, gap challenge, excerpt recovery,
event-identity, answer-coverage and structural residue filtering. Layer 50 now
runs too early to observe those later protections.

This layer restores the architectural invariant: the definitive readiness check
runs after every current Deep Recall stage. It does not change evidence or
autobiographical facts. Ordinary Recall is unchanged.
"""

POST_50_CHECKS = {
    "assertion_guard": "deep_recall_assertion_guard",
    "plan_outcome_guard": "deep_recall_plan_outcome_guard",
    "polarity_guard": "deep_recall_polarity_guard",
    "speaker_attribution": "deep_recall_speaker_attribution_guard",
    "number_unit_guard": "deep_recall_number_unit_guard",
    "response_hygiene": "deep_recall_response_hygiene",
    "gap_claim_challenge": "deep_recall_gap_claim_challenge",
    "excerpt_boundary_guard": "deep_recall_excerpt_boundary_guard",
    "excerpt_recovery": "deep_recall_excerpt_recovery",
    "event_identity_guard": "deep_recall_event_identity_guard",
    "answer_coverage": "deep_recall_final_answer_coverage_enforcement",
    "operational_filter": "deep_recall_operational_residue_filter",
}

# Excerpt recovery may legitimately report not_needed/unresolved; presence of the
# receipt is what matters here, not whether a recovery was required.
REQUIRED_PRE_50 = {
    "chain_integrity": "deep_recall_chain_integrity",
    "final_coverage": "deep_recall_final_coverage",
    "conflict_reconciliation": "deep_recall_final_conflict_reconciliation",
    "source_attribution": "deep_recall_source_attribution",
    "negative_evidence_guard": "deep_recall_negative_evidence_guard",
}


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        evidence = list(result.get("evidence") or [])
        plan = dict(result.get("recall_plan") or {})

        missing = []
        observed = {}
        for label, key in {**REQUIRED_PRE_50, **POST_50_CHECKS}.items():
            present = key in plan and plan.get(key) is not None
            observed[label] = present
            if not present:
                missing.append(label)

        chain_state = rhee.safe_text(
            plan.get("deep_recall_chain_integrity", "unknown")
        ).lower()
        thin_parts = list(plan.get("deep_recall_final_thin_parts") or [])
        operational_removed = int(
            plan.get("deep_recall_operational_residue_removed_count", 0) or 0
        )
        excerpt_recovery = rhee.safe_text(
            plan.get("deep_recall_excerpt_recovery", "unknown")
        ).lower()

        if missing or chain_state == "warning":
            readiness = "engineering_warning"
        elif thin_parts:
            readiness = "ready_with_gaps"
        else:
            readiness = "ready"

        output = dict(result)
        plan.update({
            "deep_recall_final_readiness_v2": readiness,
            "deep_recall_final_readiness_v2_version": 2,
            "deep_recall_final_readiness_v2_missing_stages": missing,
            "deep_recall_final_readiness_v2_observed": observed,
            "deep_recall_final_readiness_v2_evidence_sources": len(evidence),
            "deep_recall_final_readiness_v2_thin_parts": thin_parts,
            "deep_recall_final_readiness_v2_operational_removed": operational_removed,
            "deep_recall_final_readiness_v2_excerpt_recovery": excerpt_recovery,
        })
        output["recall_plan"] = plan

        if readiness == "ready":
            direction = (
                "READY: all required current Deep Recall stages reported execution. "
                "Compose the full evidence-supported answer."
            )
        elif readiness == "ready_with_gaps":
            direction = (
                "READY WITH GAPS: the current pipeline completed, but one or more "
                "requested parts remain thin. Present all supported stages and name "
                "only the genuine remaining gaps."
            )
        else:
            direction = (
                "ENGINEERING WARNING: one or more required current Deep Recall stages "
                "did not report execution. Do not misdescribe this as autobiographical "
                "absence. Use only the evidence actually present and expose the pipeline "
                "limitation if it materially affects the answer."
            )

        lines = [
            "DEEP RECALL FINAL READINESS GATE V2",
            f"Readiness={readiness.upper()}; final evidence sources={len(evidence)}; "
            f"thin parts={len(thin_parts)}; missing required stages={len(missing)}; "
            f"operational residue removed={operational_removed}.",
            direction,
            "This V2 gate supersedes the earlier Layer 50 readiness state because it runs after Layers 51-62.",
            "Before finishing: preserve assertion polarity, plan-vs-outcome status, speaker attribution, number/unit fidelity, event identity and excerpt boundaries; present every material supported requested stage; do not replay structurally filtered operational residue.",
            "Do not expose readiness counters or internal layer mechanics unless Doug asks for debugging details.",
        ]
        if missing:
            lines.append("Missing required runtime stages: " + ", ".join(missing))

        context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        return output

    rhee.build_context_packet = packet

    from layers.layer64_deep_recall_conflict_rescue import install as install_conflict_rescue
    install_conflict_rescue(rhee)
