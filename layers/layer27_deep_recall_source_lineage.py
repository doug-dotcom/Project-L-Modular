"""Layer 27 — Deep Recall source-lineage guard.

A raw Doug record can later appear again as promoted/canonical memory or in a
secondary summary. Those are useful representations, but they are not necessarily
independent corroboration. This layer exposes source lineage before composition
so repeated descendants of one underlying record cannot create false confidence.

No evidence is deleted and no factual conflict is resolved here. Ordinary Recall
is unchanged.
"""
from collections import Counter, defaultdict


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def raw_source_id(item):
        source = rhee.safe_text(item.get("source"))
        if source.startswith("raw_catchall:"):
            return source.split(":", 1)[1]
        raw_id = item.get("raw_id")
        if raw_id is not None and rhee.safe_text(raw_id):
            return rhee.safe_text(raw_id)
        return ""

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        evidence = list(result.get("evidence") or [])
        lineage = defaultdict(list)
        source_families = Counter()
        for item in evidence:
            source = rhee.safe_text(item.get("source"))
            family = source.split(":", 1)[0] if ":" in source else source
            source_families[family or "unknown"] += 1
            rid = raw_source_id(item)
            if rid:
                lineage[rid].append(source)

        shared = {rid: sources for rid, sources in lineage.items() if len(sources) > 1}
        unique_lineages = len(lineage) + sum(1 for item in evidence if not raw_source_id(item))

        contract_lines = [
            "DEEP RECALL SOURCE-LINEAGE CONTRACT",
            f"Evidence items: {len(evidence)}; approximate distinct evidence lineages: {unique_lineages}; shared raw-source lineages: {len(shared)}.",
            "A raw record and a promoted/canonical memory derived from that same raw_id are related representations, not automatically independent corroboration.",
            "Likewise, an assistant summary repeating Doug's statement does not become a second independent witness merely because it is stored separately.",
            "Use duplicate/derived records for organisation and context, but base confidence on the authority and independence of the underlying evidence.",
            "Do not discard a canonical memory solely because it has lineage; use it under the existing provenance rules and preserve genuine conflicts.",
        ]
        if shared:
            preview = list(shared.items())[:12]
            contract_lines.append("Shared lineage examples: " + "; ".join(
                f"raw_catchall:{rid} -> {', '.join(sources[:4])}" for rid, sources in preview
            ))

        output = dict(result)
        context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(contract_lines)
        output["context"] = context
        output["context_size"] = len(context)
        plan = dict(output.get("recall_plan") or {})
        plan.update({
            "deep_recall_source_lineage": "applied",
            "deep_recall_lineage_evidence_items": len(evidence),
            "deep_recall_lineage_approx_unique": unique_lineages,
            "deep_recall_lineage_shared_raw_ids": len(shared),
            "deep_recall_lineage_source_families": dict(source_families),
        })
        output["recall_plan"] = plan
        return output

    rhee.build_context_packet = packet
