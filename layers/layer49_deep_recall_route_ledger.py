"""Layer 49 — Deep Recall retrieval-loop deduplication ledger.

Deep Recall now has many rescue paths that can rediscover the same source for
different reasons. The evidence list itself is source-deduplicated by most
layers, but diagnostics and composition can still overvalue a record simply
because it was reached through several retrieval routes.

This final ledger records the retrieval reasons attached to each source and
reinforces that multi-path discovery is useful for coverage, not independent
corroboration. It changes no evidence and does not affect ordinary Recall.
"""
from collections import defaultdict

ROUTE_KEYS = {
    "multi_angle": "deep_recall_angle",
    "gap_rescue": "deep_recall_gap",
    "anchor_followthrough": "deep_recall_anchor",
    "correction_hunt": "deep_recall_correction_candidate",
    "component_rescue": "deep_recall_component",
    "provenance_backfill": "deep_recall_provenance_backfill",
    "time_window": "deep_recall_time_window",
    "alias_bridge": "deep_recall_alias",
    "transition_rescue": "deep_recall_transition",
}


def install(rhee):
    previous_packet = rhee.build_context_packet

    def explicit_deep(query):
        return rhee.term_in_text("deep recall", rhee.safe_text(query).lower())

    def packet(query):
        result = previous_packet(query)
        if not explicit_deep(query):
            return result

        evidence = list(result.get("evidence") or [])
        routes = defaultdict(list)
        for item in evidence:
            source = rhee.safe_text(item.get("source")).strip()
            if not source:
                continue
            for label, key in ROUTE_KEYS.items():
                if item.get(key):
                    routes[source].append(label)
            if not routes[source]:
                routes[source].append("base_or_breadth")

        multi_route = {
            source: sorted(set(labels))
            for source, labels in routes.items()
            if len(set(labels)) > 1
        }
        route_counts = defaultdict(int)
        for labels in routes.values():
            for label in set(labels):
                route_counts[label] += 1

        output = dict(result)
        plan = dict(output.get("recall_plan") or {})
        plan.update({
            "deep_recall_retrieval_route_ledger": "applied",
            "deep_recall_retrieval_route_counts": dict(route_counts),
            "deep_recall_multi_route_source_count": len(multi_route),
            "deep_recall_multi_route_source_preview": [
                {"source": source, "routes": labels}
                for source, labels in list(multi_route.items())[:30]
            ],
        })
        output["recall_plan"] = plan

        lines = [
            "DEEP RECALL RETRIEVAL-ROUTE DEDUPLICATION LEDGER",
            f"Unique evidence sources={len(routes)}; sources reached/marked through multiple retrieval routes={len(multi_route)}.",
            "A source found through multiple routes is a useful sign that several search strategies converged on it, but it remains ONE source and ONE evidence lineage unless independent evidence establishes otherwise.",
            "Do not increase factual confidence merely because the same record was relevant to a gap rescue, alias search, time-window search and transition search.",
            "Use route convergence to understand retrieval coverage and salience, not as a vote count.",
            "Source lineage, primary authority, corrections and independent corroboration remain the confidence controls.",
        ]

        context = rhee.safe_text(output.get("context")) + "\n\n" + "\n".join(lines)
        output["context"] = context
        output["context_size"] = len(context)
        return output

    rhee.build_context_packet = packet
