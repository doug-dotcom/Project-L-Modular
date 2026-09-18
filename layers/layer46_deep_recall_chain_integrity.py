"""Layer 46 — Deep Recall chain-integrity sentinel.

The recall architecture now has many cooperating layers. A file can exist and
deploy successfully while still being accidentally disconnected from the active
install chain, as happened earlier with the first retrieval receipt.

This final diagnostic sentinel checks for the expected runtime receipts produced
by the major Deep Recall stages. It does not alter evidence, retry searches or
affect ordinary Recall. Missing receipts are surfaced as an engineering warning,
not as an autobiographical limitation.
"""

EXPECTED = {
    "subject_fidelity": "deep_recall_subject_fidelity",
    "question_decomposition": "deep_recall_question_decomposition",
    "component_rescue": "deep_recall_component_rescue",
    "provenance_backfill": "deep_recall_provenance_backfill",
    "time_window_rescue": "deep_recall_time_window_rescue",
    "alias_bridge": "deep_recall_alias_bridge",
    "transition_rescue": "deep_recall_transition_rescue",
    "late_match_centering": "deep_recall_late_match_centering",
    "final_coverage": "deep_recall_final_coverage",
    "chronology_confidence": "deep_recall_chronology_confidence",
    "final_conflict_reconciliation": "deep_recall_final_conflict_reconciliation",
    "primary_singletons": "deep_recall_primary_singleton_preservation",
    "source_attribution": "deep_recall_source_attribution",
    "context_budget": "deep_recall_context_budget_governor",
    "negative_evidence_guard": "deep_recall_negative_evidence_guard",
    "stale_summary_quarantine": "deep_recall_stale_summary_quarantine",
}

# Some layers are conditional by design and may legitimately leave no receipt
# when their trigger is absent. They are checked only when the request requires
# their trigger.
CONDITIONAL = {
    "component_rescue",
    "time_window_rescue",
    "transition_rescue",
    "late_match_centering",
}


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        plan = dict(result.get("recall_plan") or {})
        present = {}
        missing = []

        for label, key in EXPECTED.items():
            value = plan.get(key)
            present[label] = value is not None
            if value is None and label not in CONDITIONAL:
                missing.append(label)

        output = dict(result)
        plan.update({
            "deep_recall_chain_integrity": "ok" if not missing else "warning",
            "deep_recall_chain_integrity_present": present,
            "deep_recall_chain_integrity_missing_required": missing,
            "deep_recall_chain_integrity_expected_count": len(EXPECTED),
            "deep_recall_chain_integrity_present_count": sum(present.values()),
        })
        output["recall_plan"] = plan

        # Keep this deliberately tiny: Layer 43 exists because diagnostic prose
        # must not crowd out source evidence.
        if missing:
            warning = (
                "\n\nDEEP RECALL ENGINEERING INTEGRITY WARNING\n"
                "One or more expected Deep Recall runtime receipts were not observed: "
                + ", ".join(missing)
                + ". Do not interpret this as missing autobiographical evidence. "
                "Answer only from retrieved evidence and expose the retrieval limitation if it materially affects the result."
            )
            context = rhee.safe_text(output.get("context")) + warning
            output["context"] = context
            output["context_size"] = len(context)

        return output

    rhee.build_context_packet = packet
