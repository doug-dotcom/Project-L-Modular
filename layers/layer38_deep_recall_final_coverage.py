"""Layer 38 — final Deep Recall coverage reconciliation.

Several late rescue passes can materially improve coverage after the earlier
coverage/self-audit layers have already run. This layer performs one final
evidence-only reconciliation at the end of retrieval so composition knows which
explicit question parts are now represented and which remain genuinely thin.

It does not launch another search, create facts or infer that a thin component
was never stored. Ordinary Recall is unchanged.
"""

MIN_SUPPORTING_ITEMS = 2


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def score_item(item, part):
        text = rhee.safe_text(item.get("quote_source"))
        if not text:
            return 0
        try:
            return rhee.calculate_raw_score(
                {"content": text, "role": item.get("role", "unknown")},
                part,
            )
        except Exception:
            return 0

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        evidence = list(result.get("evidence") or [])
        plan = dict(result.get("recall_plan") or {})
        parts = list(plan.get("deep_recall_question_parts") or [])
        if not parts:
            subject = rhee.safe_text(plan.get("deep_recall_original_subject")).strip()
            parts = [subject] if subject else [rhee.safe_text(query)]

        coverage = {}
        represented = []
        thin = []
        for part in parts:
            supporting = sum(1 for item in evidence if score_item(item, part) > 0)
            coverage[part] = supporting
            if supporting >= MIN_SUPPORTING_ITEMS:
                represented.append(part)
            else:
                thin.append(part)

        output = dict(result)
        plan.update({
            "deep_recall_final_coverage": "reconciled",
            "deep_recall_final_component_coverage": coverage,
            "deep_recall_final_represented_parts": represented,
            "deep_recall_final_thin_parts": thin,
            "deep_recall_final_coverage_complete": not thin,
        })
        output["recall_plan"] = plan

        lines = [
            "DEEP RECALL FINAL COVERAGE RECONCILIATION",
            "This check occurs after all current rescue passes, so it supersedes earlier provisional coverage impressions.",
        ]
        for part in parts:
            state = "REPRESENTED" if part in represented else "THIN"
            lines.append(f"- {state}: {part} ({coverage.get(part, 0)} supporting evidence item(s) by retrieval scoring)")
        lines.extend([
            "A REPRESENTED component still requires claim-level evidence checking; count alone does not prove every detail.",
            "A THIN component means this completed retrieval did not establish enough evidence for that requested part. It does NOT mean the memory was never stored or the event never happened.",
            "Compose the supported answer fully, and identify only the remaining genuinely thin requested parts rather than repeating gaps that later rescue passes have already filled.",
        ])

        context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        return output

    rhee.build_context_packet = packet
