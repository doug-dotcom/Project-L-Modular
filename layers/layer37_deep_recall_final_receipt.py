"""Layer 37 — final Deep Recall execution receipt v2.

Layer 29 introduced observability, but the Deep Recall chain has since gained
question decomposition, component rescue, provenance backfill, time-window
rescue, alias bridging, transition rescue and late match-centring. Because those
passes run after Layer 29, its receipt cannot describe the final retrieval state.

This layer emits a final receipt after all current retrieval passes. Diagnostic
metadata only: no evidence or autobiographical facts are changed.
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

        receipt = {
            "version": 2,
            "mode": "deep_recall",
            "evidence_sources_final": len(evidence),
            "primary_user_sources_final": sum(
                1 for item in evidence
                if rhee.safe_text(item.get("role")).lower() == "user"
            ),
            "breadth_added": as_int(plan.get("deep_recall_raw_added")) + as_int(plan.get("deep_recall_memory_added")),
            "multi_angle_added": as_int(plan.get("deep_recall_multi_angle_added")),
            "gap_rescue_added": as_int(plan.get("deep_recall_gap_rescue_added")),
            "anchor_followthrough_added": as_int(plan.get("deep_recall_anchor_added")),
            "correction_candidates_added": as_int(plan.get("deep_recall_correction_candidates_added")),
            "component_rescue_added": as_int(plan.get("deep_recall_component_added")),
            "provenance_backfill_added": as_int(plan.get("deep_recall_provenance_added")),
            "time_window_added": as_int(plan.get("deep_recall_time_window_added")),
            "alias_bridge_added": as_int(plan.get("deep_recall_alias_added")),
            "transition_rescue_added": as_int(plan.get("deep_recall_transition_added")),
            "late_match_windows": as_int(plan.get("deep_recall_late_match_windows")),
            "near_duplicates_suppressed": as_int(plan.get("deep_recall_near_duplicates_suppressed")),
            "shared_raw_lineages": as_int(plan.get("deep_recall_lineage_shared_raw_ids")),
            "question_parts": list(plan.get("deep_recall_question_parts") or []),
            "thin_components": list(plan.get("deep_recall_component_thin_parts") or []),
            "saturation": plan.get("deep_recall_saturation", "unknown"),
            "answer_depth": plan.get("deep_recall_answer_depth", "unknown"),
            "subject_fidelity": plan.get("deep_recall_subject_fidelity", "unknown"),
            "claim_evidence_contract": plan.get("deep_recall_claim_evidence_contract", "unknown"),
            "temporal_truth": plan.get("deep_recall_temporal_truth", "unknown"),
        }

        output = dict(result)
        plan["deep_recall_final_receipt"] = receipt
        plan["deep_recall_receipt_version"] = 2
        output["recall_plan"] = plan

        context = rhee.safe_text(output.get("context"))
        context += (
            "\n\nDEEP RECALL FINAL EXECUTION RECEIPT V2\n"
            f"Final evidence={receipt['evidence_sources_final']}; primary_user={receipt['primary_user_sources_final']}; "
            f"component_added={receipt['component_rescue_added']}; provenance_added={receipt['provenance_backfill_added']}; "
            f"time_window_added={receipt['time_window_added']}; alias_added={receipt['alias_bridge_added']}; "
            f"transition_added={receipt['transition_rescue_added']}; late_match_windows={receipt['late_match_windows']}.\n"
            "This is diagnostic metadata only. It describes which retrieval machinery ran and what it contributed; "
            "never present these counters as facts about Doug's life."
        )
        output["context"] = context
        output["context_size"] = len(context)
        return output

    rhee.build_context_packet = packet

    from layers.layer38_deep_recall_final_coverage import install as install_final_coverage
    install_final_coverage(rhee)
