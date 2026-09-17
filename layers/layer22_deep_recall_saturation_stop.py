"""Layer 22 — Deep Recall saturation / diminishing-returns stop.

Deep Recall is deliberately patient, but patience should buy evidence rather than
endless repeated searching. After the full-corpus, multi-angle, gap-rescue and
anchor-follow-through passes, provide a compact saturation signal so composition
can distinguish a productive broad search from a search that has reached
diminishing returns.

This layer never treats saturation as proof that an absent fact is not stored.
It does not remove evidence or shorten ordinary Recall.
"""


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        plan = dict(result.get("recall_plan") or {})
        multi = int(plan.get("deep_recall_multi_angle_added", 0) or 0)
        gap = int(plan.get("deep_recall_gap_rescue_added", 0) or 0)
        anchor = int(plan.get("deep_recall_anchor_added", 0) or 0)
        primary = int(plan.get("deep_recall_primary_sources_added", 0) or 0)
        breadth = int(plan.get("deep_recall_raw_added", 0) or 0) + int(plan.get("deep_recall_memory_added", 0) or 0)

        late_yield = multi + gap + anchor
        if late_yield == 0:
            state = "saturated"
        elif late_yield <= 4:
            state = "near_saturation"
        else:
            state = "productive"

        plan.update({
            "deep_recall_saturation": state,
            "deep_recall_late_pass_new_sources": late_yield,
            "deep_recall_total_expansion_sources": breadth + primary + late_yield,
        })

        output = dict(result)
        output["recall_plan"] = plan
        context = rhee.safe_text(output.get("context"))
        context += (
            "\n\nDEEP RECALL SATURATION CHECK\n"
            f"Late retrieval passes added {late_yield} distinct source(s); saturation state={state}.\n"
            "If PRODUCTIVE, use the added evidence normally. If NEAR_SATURATION or SATURATED, do not keep conceptually chasing the same archive indefinitely: compose the best evidence-supported answer and clearly name genuinely thin areas. "
            "Saturation means the current retrieval strategy found few new distinct records; it does NOT prove that a missing fact was never stored."
        )
        output["context"] = context
        output["context_size"] = len(context)
        return output

    rhee.build_context_packet = packet

    from layers.layer23_deep_recall_correction_hunt import install as install_correction_hunt
    install_correction_hunt(rhee)
