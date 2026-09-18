"""Layer 47 — Deep Recall interpretation-provenance firewall.

Autobiographical archives contain both facts Doug reported and interpretations
written later by assistants: psychological meaning, causal explanations,
characterisations and narrative themes. A polished interpretation must not
silently become a remembered fact about Doug.

This final composition guard identifies interpretation/causality language in
secondary evidence and requires L to keep retrieved fact, Doug's own reflection,
and assistant synthesis visibly distinct. It does not ban interpretation or
discard useful summaries. Ordinary Recall is unchanged.
"""
import re

INTERPRETIVE_RE = re.compile(
    r"\b(?:my interpretation|interpretation|suggests?|indicates?|implies?|"
    r"likely|probably|perhaps|may have|might have|appears? to|seems? to|"
    r"because of|caused|led to|shaped|explains?|reflects?|represents?|"
    r"nervous system learned|trauma response|attachment|coping mechanism|"
    r"this means|the pattern|underlying|subconscious)\b",
    re.I,
)


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        evidence = list(result.get("evidence") or [])
        secondary_interpretations = []
        user_reflections = []

        for item in evidence:
            source = rhee.safe_text(item.get("source"))
            role = rhee.safe_text(item.get("role")).lower()
            text = rhee.safe_text(item.get("quote_source"))
            if not INTERPRETIVE_RE.search(text):
                continue
            if role == "user":
                user_reflections.append(source)
            else:
                secondary_interpretations.append(source)

        output = dict(result)
        plan = dict(output.get("recall_plan") or {})
        plan.update({
            "deep_recall_interpretation_firewall": "applied",
            "deep_recall_secondary_interpretation_sources": secondary_interpretations[:40],
            "deep_recall_user_reflection_sources": user_reflections[:40],
            "deep_recall_secondary_interpretation_count": len(secondary_interpretations),
            "deep_recall_user_reflection_count": len(user_reflections),
        })
        output["recall_plan"] = plan

        lines = [
            "DEEP RECALL INTERPRETATION-PROVENANCE FIREWALL",
            f"Secondary interpretation-like sources detected={len(secondary_interpretations)}; Doug-authored reflection-like sources={len(user_reflections)}.",
            "Keep three things distinct in the final answer: (1) concrete autobiographical facts supported by retrieved evidence, (2) Doug's own stated reflections/interpretations, and (3) assistant/system synthesis or interpretation.",
            "Do not convert an assistant's psychological, causal or narrative interpretation into a factual memory about Doug merely because it was stored in the archive.",
            "If Doug himself stated an interpretation, attribute it as Doug's reflection unless the evidence independently establishes it as fact.",
            "Causal claims such as 'X caused Y', psychological explanations, motives and nervous-system narratives require evidence appropriate to that claim; chronological proximity alone is not causation.",
            "Assistant interpretations may still be useful when clearly labelled as interpretation and consistent with the evidence, but they do not outrank Doug-authored primary facts.",
            "When a concrete fact and an interpretation appear in the same source, preserve the fact without automatically inheriting the interpretation.",
        ]
        if secondary_interpretations:
            lines.append(
                "Secondary interpretation sources for caution: " +
                ", ".join(secondary_interpretations[:40])
            )

        context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        return output

    rhee.build_context_packet = packet
