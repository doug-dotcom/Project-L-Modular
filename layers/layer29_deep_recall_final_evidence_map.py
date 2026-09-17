"""Layer 29 — Deep Recall final evidence map.

After all expansion passes, Deep Recall can hold a large packet from many routes.
Before composition, build a compact map of which records are primary, derived,
correction candidates, gap rescues, anchor follow-through, multi-angle finds and
ordinary retrieval. This gives the answer model a navigable evidence index rather
than asking it to reason over a large undifferentiated pile.

The map does not delete, promote or create evidence. Ordinary Recall is unchanged.
"""
from collections import Counter

MAX_PREVIEW = 36


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def route(item):
        if item.get("deep_recall_correction_candidate"):
            return "correction_candidate"
        if item.get("deep_recall_gap"):
            return "gap_rescue"
        if item.get("deep_recall_anchor"):
            return "anchor_followthrough"
        if item.get("deep_recall_angle"):
            return "multi_angle"
        if item.get("deep_recall_primary_score") is not None:
            return "primary_reserve"
        if item.get("deep_recall_score") is not None:
            return "breadth_pass"
        return "base_retrieval"

    def authority(item):
        role = rhee.safe_text(item.get("role")).lower()
        source = rhee.safe_text(item.get("source")).lower()
        if role == "user":
            return "doug_primary"
        if role in {"assistant", "model"}:
            return "assistant_secondary"
        if source.startswith("memory_") or source.startswith("episodic_memories") or source.startswith("identity_anchors"):
            return "governed_memory"
        return "other"

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        evidence = list(result.get("evidence") or [])
        routes = Counter(route(item) for item in evidence)
        authorities = Counter(authority(item) for item in evidence)

        # Put primary/correction evidence first in the compact preview, then
        # retain original packet order. This is only a navigation aid.
        def preview_key(pair):
            idx, item = pair
            a = authority(item)
            r = route(item)
            return (
                0 if a == "doug_primary" else 1,
                0 if r == "correction_candidate" else 1,
                idx,
            )

        preview = sorted(enumerate(evidence), key=preview_key)[:MAX_PREVIEW]
        lines = [
            "DEEP RECALL FINAL EVIDENCE MAP",
            f"Total evidence items available: {len(evidence)}.",
            "Retrieval routes: " + (", ".join(f"{k}={v}" for k, v in routes.most_common()) or "none"),
            "Authority classes: " + (", ".join(f"{k}={v}" for k, v in authorities.most_common()) or "none"),
            "Use this map to navigate the packet; it is not a substitute for reading the source-linked evidence.",
            "Prioritise Doug-primary evidence and explicit corrections, then governed memory, while applying the existing conflict, temporal, lineage and claim-evidence contracts.",
            "Evidence preview:",
        ]
        for _, item in preview:
            lines.append(
                f"- {rhee.safe_text(item.get('source'))} | authority={authority(item)} | route={route(item)}"
            )

        output = dict(result)
        context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        plan = dict(output.get("recall_plan") or {})
        plan.update({
            "deep_recall_final_evidence_map": "applied",
            "deep_recall_final_evidence_items": len(evidence),
            "deep_recall_final_routes": dict(routes),
            "deep_recall_final_authorities": dict(authorities),
        })
        output["recall_plan"] = plan
        return output

    rhee.build_context_packet = packet
