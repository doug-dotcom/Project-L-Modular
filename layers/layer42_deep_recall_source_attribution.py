"""Layer 42 — Deep Recall source-attribution completeness.

Deep Recall now retrieves and reconciles a large evidence packet. The final
answer must remain auditable: a detailed biography is much easier to trust and
debug when each major stage or concrete factual cluster identifies the retrieved
source(s) supporting it.

This composition contract requires source attribution close to material claims.
It does not invent citations, require a citation after every sentence, or change
ordinary Recall.
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
        valid_sources = []
        seen = set()
        for item in evidence:
            source = rhee.safe_text(item.get("source")).strip()
            if source and source not in seen:
                valid_sources.append(source)
                seen.add(source)

        output = dict(result)
        plan = dict(output.get("recall_plan") or {})
        plan.update({
            "deep_recall_source_attribution": "required",
            "deep_recall_source_attribution_available_sources": len(valid_sources),
            "deep_recall_source_attribution_source_preview": valid_sources[:40],
        })
        output["recall_plan"] = plan

        lines = [
            "DEEP RECALL SOURCE-ATTRIBUTION COMPLETENESS CONTRACT",
            f"Retrieved source identifiers available for attribution: {len(valid_sources)}.",
            "Keep the final answer auditable. For each major stage, transition, or cluster of concrete autobiographical facts, identify the retrieved source or sources that actually support it using Project L's existing source-display format.",
            "Place attribution close enough to the supported claim that Doug can tell what evidence belongs to what part of the answer.",
            "Do not cite a source merely because it is topically related; the quoted/retrieved content must support the claim being attributed.",
            "Do not invent source IDs, line numbers, quotations or provenance that are not present in the evidence packet.",
            "Several compatible claims supported by the same source may share one attribution; do not turn the answer into a citation dump.",
            "When a paragraph contains both retrieved fact and interpretation, make that distinction clear so the source attribution is not presented as proving the interpretation.",
            "For a genuinely thin requested part, name the retrieval gap rather than attaching an unrelated source to make the answer look complete.",
            "Source count is not confidence: lineage, primary authority, corrections, chronology and conflict rules remain controlling.",
        ]

        context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        return output

    rhee.build_context_packet = packet
