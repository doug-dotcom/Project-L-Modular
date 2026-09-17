"""Layer 29 — Deep Recall retrieval receipt / observability.

Deep Recall now has many cooperating passes. When a test succeeds or fails we
need to know what actually ran, rather than infer it from the prose answer. This
layer creates a compact, stable receipt in recall_plan from the instrumentation
already produced by earlier layers.

The receipt is diagnostic metadata only. It does not add facts, change evidence,
or affect ordinary Recall.
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
            "mode": "deep_recall",
            "full_corpus": plan.get("deep_recall_full_corpus", plan.get("deep_recall_mode", "requested")),
            "evidence_sources": len(evidence),
            "primary_user_sources": sum(1 for item in evidence if rhee.safe_text(item.get("role")).lower() == "user"),
            "breadth_added": as_int(plan.get("deep_recall_raw_added")) + as_int(plan.get("deep_recall_memory_added")),
            "multi_angle_added": as_int(plan.get("deep_recall_multi_angle_added")),
            "gap_rescue_added": as_int(plan.get("deep_recall_gap_rescue_added")),
            "anchor_followthrough_added": as_int(plan.get("deep_recall_anchor_added")),
            "correction_candidates_added": as_int(plan.get("deep_recall_correction_candidates_added")),
            "near_duplicates_suppressed": as_int(plan.get("deep_recall_near_duplicates_suppressed")),
            "shared_raw_lineages": as_int(plan.get("deep_recall_lineage_shared_raw_ids")),
            "saturation": plan.get("deep_recall_saturation", "unknown"),
            "answer_depth": plan.get("deep_recall_answer_depth", "unknown"),
            "subject_fidelity": plan.get("deep_recall_subject_fidelity", "unknown"),
            "claim_evidence_contract": plan.get("deep_recall_claim_evidence_contract", "unknown"),
            "temporal_truth": plan.get("deep_recall_temporal_truth", "unknown"),
        }

        plan["deep_recall_receipt"] = receipt
        plan["deep_recall_receipt_version"] = 1
        output = dict(result)
        output["recall_plan"] = plan

        context = rhee.safe_text(output.get("context"))
        context += (
            "\n\nDEEP RECALL EXECUTION RECEIPT\n"
            f"Evidence={receipt['evidence_sources']}; primary_user={receipt['primary_user_sources']}; "
            f"breadth_added={receipt['breadth_added']}; multi_angle_added={receipt['multi_angle_added']}; "
            f"gap_rescue_added={receipt['gap_rescue_added']}; anchor_added={receipt['anchor_followthrough_added']}; "
            f"corrections_added={receipt['correction_candidates_added']}; saturation={receipt['saturation']}.\n"
            "This receipt is diagnostic. Do not present its counters as autobiographical facts. "
            "Use it to recognise whether the intended Deep Recall machinery actually ran and to make future failures debuggable without guessing."
        )
        output["context"] = context
        output["context_size"] = len(context)
        return output

    rhee.build_context_packet = packet
