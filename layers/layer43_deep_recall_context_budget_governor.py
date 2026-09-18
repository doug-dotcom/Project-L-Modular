"""Layer 43 — Deep Recall final context-budget governor.

Deep Recall deliberately carries far more evidence than ordinary Recall. After
many rescue and audit layers, however, diagnostic contracts themselves can start
competing with autobiographical evidence for model context. This governor keeps
Deep Recall patient and rich while making the final packet budget-aware.

It never removes source evidence or changes retrieval. Instead it emits a compact
budget receipt and instructs composition to prioritise source-linked evidence
over repeated diagnostic prose if the context is large. Ordinary Recall is
unchanged.
"""

SOFT_CONTEXT_CHARS = 220000
HIGH_CONTEXT_CHARS = 320000


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        context = rhee.safe_text(result.get("context"))
        evidence = list(result.get("evidence") or [])
        evidence_chars = sum(
            len(rhee.safe_text(item.get("quote_source"))) for item in evidence
        )
        total_chars = len(context)

        if total_chars >= HIGH_CONTEXT_CHARS:
            pressure = "high"
        elif total_chars >= SOFT_CONTEXT_CHARS:
            pressure = "elevated"
        else:
            pressure = "normal"

        output = dict(result)
        plan = dict(output.get("recall_plan") or {})
        plan.update({
            "deep_recall_context_budget_governor": "applied",
            "deep_recall_context_pressure": pressure,
            "deep_recall_context_chars_final": total_chars,
            "deep_recall_evidence_chars_final": evidence_chars,
            "deep_recall_evidence_sources_final_budget": len(evidence),
        })
        output["recall_plan"] = plan

        contract = (
            "\n\nDEEP RECALL FINAL CONTEXT-BUDGET GOVERNOR\n"
            f"Context pressure={pressure}; final context chars={total_chars}; "
            f"source-evidence chars={evidence_chars}; evidence sources={len(evidence)}.\n"
            "Deep Recall trades speed for depth, but diagnostic instructions must never crowd out the evidence they are meant to protect. "
            "When composing, prioritise source-linked autobiographical evidence, explicit user corrections, final coverage findings and unresolved conflicts over repeated or redundant diagnostic prose. "
            "Do not shorten a well-supported answer merely because the retrieval was expensive. "
            "Do not dump diagnostic contracts or counters into the user-facing answer unless Doug explicitly asks for debugging details. "
            "If context pressure is elevated/high, synthesise repeated evidence and repeated instructions rather than dropping unique primary facts. "
            "This governor does not authorise invention, silent conflict resolution or removal of material evidence."
        )
        output["context"] = context + contract
        output["context_size"] = len(output["context"])
        return output

    rhee.build_context_packet = packet
