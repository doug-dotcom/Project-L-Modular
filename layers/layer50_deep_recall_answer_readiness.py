"""Layer 50 — Deep Recall answer-readiness gate.

Milestone layer: after retrieval, rescue, provenance, chronology, conflict,
coverage, attribution and integrity checks have all had their turn, Deep Recall
needs one final decision about how the answer may be composed.

This gate does not decide whether Doug's memories are true and it never blocks a
supported answer merely because some requested detail remains thin. It classifies
the completed retrieval as READY, READY_WITH_GAPS, or ENGINEERING_WARNING and
gives composition a single final contract. Ordinary Recall is unchanged.
"""


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

        chain_state = rhee.safe_text(
            plan.get("deep_recall_chain_integrity", "unknown")
        ).lower()
        thin_parts = list(plan.get("deep_recall_final_thin_parts") or [])
        coverage_complete = bool(
            plan.get("deep_recall_final_coverage_complete", not thin_parts)
        )
        attribution = rhee.safe_text(
            plan.get("deep_recall_source_attribution", "unknown")
        ).lower()
        conflict_review = rhee.safe_text(
            plan.get("deep_recall_final_conflict_reconciliation", "unknown")
        ).lower()
        negative_guard = rhee.safe_text(
            plan.get("deep_recall_negative_evidence_guard", "unknown")
        ).lower()
        entity_guard = rhee.safe_text(
            plan.get("deep_recall_entity_fidelity", "unknown")
        ).lower()
        interpretation_guard = rhee.safe_text(
            plan.get("deep_recall_interpretation_firewall", "unknown")
        ).lower()

        engineering_warning = chain_state == "warning"
        if engineering_warning:
            readiness = "engineering_warning"
        elif not coverage_complete or thin_parts:
            readiness = "ready_with_gaps"
        else:
            readiness = "ready"

        checks = {
            "has_evidence": bool(evidence),
            "chain_integrity": chain_state,
            "coverage_complete": coverage_complete,
            "thin_parts": thin_parts,
            "source_attribution": attribution,
            "conflict_reconciliation": conflict_review,
            "negative_evidence_guard": negative_guard,
            "entity_fidelity": entity_guard,
            "interpretation_firewall": interpretation_guard,
        }

        output = dict(result)
        plan.update({
            "deep_recall_answer_readiness": readiness,
            "deep_recall_answer_readiness_version": 1,
            "deep_recall_answer_readiness_checks": checks,
            "deep_recall_answer_readiness_evidence_sources": len(evidence),
        })
        output["recall_plan"] = plan

        if readiness == "ready":
            direction = (
                "READY: compose the requested Deep Recall fully from the retrieved "
                "evidence. Preserve uncertainty only where the evidence itself requires it."
            )
        elif readiness == "ready_with_gaps":
            direction = (
                "READY WITH GAPS: give Doug the full supported answer. Clearly identify "
                "only the requested parts that remain thin after all rescue passes. "
                "Do not downgrade well-supported sections because another section is thin."
            )
        else:
            direction = (
                "ENGINEERING WARNING: use only the evidence actually retrieved. If the "
                "missing runtime stage could materially affect the answer, say that the "
                "Deep Recall retrieval pipeline was incomplete rather than describing "
                "the autobiographical memory as absent."
            )

        lines = [
            "DEEP RECALL LAYER 50 — FINAL ANSWER-READINESS GATE",
            f"Readiness={readiness.upper()}; evidence sources={len(evidence)}; "
            f"final thin requested parts={len(thin_parts)}; chain integrity={chain_state}.",
            direction,
            "Final composition order: answer Doug's actual question first; use primary/source-linked evidence; preserve exact entities and chronology; apply later corrections; expose unresolved same-fact conflicts; separate Doug's reflections from assistant interpretation; keep source attribution auditable.",
            "Never convert retrieval failure into 'Doug never told me'. Never inflate confidence from duplicate lineages, repeated summaries or multiple retrieval routes.",
            "Do not expose internal receipts, counters or layer mechanics unless Doug asks for debugging detail.",
            "This readiness gate is about whether the completed evidence packet can support an answer. It is not a truth score, memory score, psychological assessment or confidence percentage.",
        ]

        context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        return output

    rhee.build_context_packet = packet

    from layers.layer51_deep_recall_assertion_guard import install as install_assertion_guard
    install_assertion_guard(rhee)
